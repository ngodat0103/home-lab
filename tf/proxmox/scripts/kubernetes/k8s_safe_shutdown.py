#!/usr/bin/env python3
"""
Kubernetes Node Drain with Longhorn Storage and Argo CD Integration

This script safely drains Kubernetes nodes by:
1. Discovering PVC-related workloads
2. Handling Argo CD managed applications
3. Quiescing workloads using PVCs
4. Detaching Longhorn volumes
5. Draining nodes systematically
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
import typer
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from loguru import logger
from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib3.util.retry import Retry

app = typer.Typer()

@dataclass
class CheckpointData:
    """Stores state for resume/restore operations"""
    timestamp: str
    nodes: List[Dict[str, Any]]
    pvc_workload_mapping: Dict[str, Dict[str, Any]]
    original_replicas: Dict[str, Dict[str, Any]]
    original_argo_policies: Dict[str, Dict[str, Any]]
    longhorn_volumes: List[Dict[str, Any]]
    operation_phase: str = "preflight"

class KubernetesHelper:
    """Helper class for Kubernetes operations"""
    
    def __init__(self):
        config.load_kube_config()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.custom_objects = client.CustomObjectsApi()
        self.api_client = client.ApiClient()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_nodes(self, node_selector: Optional[str] = None) -> List[client.V1Node]:
        """Get nodes with optional label selector"""
        try:
            if node_selector:
                nodes = self.core_v1.list_node(label_selector=node_selector)
            else:
                nodes = self.core_v1.list_node()
            return nodes.items
        except ApiException as e:
            logger.error(f"Failed to get nodes: {e}")
            raise
    
    def verify_permissions(self) -> bool:
        """Verify cluster-admin permissions"""
        try:
            # Test cluster-level operations
            self.core_v1.list_node()
            self.core_v1.list_persistent_volume()
            self.apps_v1.list_deployment_for_all_namespaces()
            
            # Test custom resource access
            try:
                self.custom_objects.list_cluster_custom_object(
                    group="longhorn.io",
                    version="v1beta2",
                    plural="volumes"
                )
            except ApiException as e:
                if e.status == 404:
                    logger.warning("Longhorn CRDs not found")
                    return False
                raise
            
            return True
        except ApiException as e:
            logger.error(f"Permission verification failed: {e}")
            return False
    
    def get_pvcs_and_pods(self) -> Dict[str, Dict[str, Any]]:
        """Map PVCs to pods and their controllers"""
        pvc_mapping = {}
        
        # Get all PVCs
        pvcs = self.core_v1.list_persistent_volume_claim_for_all_namespaces()
        
        for pvc in pvcs.items:
            if pvc.status.phase != "Bound":
                continue
            
            pvc_key = f"{pvc.metadata.namespace}/{pvc.metadata.name}"
            pvc_mapping[pvc_key] = {
                "pvc": pvc,
                "pods": [],
                "controllers": set()
            }
            
            # Find pods using this PVC
            pods = self.core_v1.list_pod_for_all_namespaces()
            for pod in pods.items:
                if pod.spec.volumes:
                    for volume in pod.spec.volumes:
                        if (volume.persistent_volume_claim and 
                            volume.persistent_volume_claim.claim_name == pvc.metadata.name and
                            pod.metadata.namespace == pvc.metadata.namespace):
                            
                            pvc_mapping[pvc_key]["pods"].append(pod)
                            
                            # Walk owner references to find top-level controller
                            controller = self._find_top_level_controller(pod)
                            if controller:
                                pvc_mapping[pvc_key]["controllers"].add(controller)
        
        # Convert sets to lists for JSON serialization
        for key in pvc_mapping:
            pvc_mapping[key]["controllers"] = list(pvc_mapping[key]["controllers"])
        
        return pvc_mapping
    
    def _find_top_level_controller(self, pod: client.V1Pod) -> Optional[str]:
        """Walk owner references to find top-level controller"""
        current_obj = pod
        visited = set()
        
        while current_obj and current_obj.metadata.owner_references:
            owner_ref = current_obj.metadata.owner_references[0]
            owner_key = f"{owner_ref.kind}/{current_obj.metadata.namespace}/{owner_ref.name}"
            
            if owner_key in visited:
                logger.warning(f"Circular reference detected: {owner_key}")
                break
            visited.add(owner_key)
            
            try:
                if owner_ref.kind == "ReplicaSet":
                    rs = self.apps_v1.read_namespaced_replica_set(
                        owner_ref.name, current_obj.metadata.namespace
                    )
                    current_obj = rs
                elif owner_ref.kind == "Deployment":
                    return f"Deployment/{current_obj.metadata.namespace}/{owner_ref.name}"
                elif owner_ref.kind == "StatefulSet":
                    return f"StatefulSet/{current_obj.metadata.namespace}/{owner_ref.name}"
                elif owner_ref.kind == "DaemonSet":
                    return f"DaemonSet/{current_obj.metadata.namespace}/{owner_ref.name}"
                elif owner_ref.kind == "Job":
                    return f"Job/{current_obj.metadata.namespace}/{owner_ref.name}"
                elif owner_ref.kind == "CronJob":
                    return f"CronJob/{current_obj.metadata.namespace}/{owner_ref.name}"
                else:
                    return f"{owner_ref.kind}/{current_obj.metadata.namespace}/{owner_ref.name}"
            except ApiException:
                break
        
        return None
    
    def is_argo_managed(self, controller_str: str) -> Optional[str]:
        """Check if controller is managed by Argo CD"""
        kind, namespace, name = controller_str.split("/", 2)
        
        try:
            if kind == "Deployment":
                obj = self.apps_v1.read_namespaced_deployment(name, namespace)
            elif kind == "StatefulSet":
                obj = self.apps_v1.read_namespaced_stateful_set(name, namespace)
            else:
                return None
            
            annotations = obj.metadata.annotations or {}
            if annotations.get("argocd.argoproj.io/tracking-id") != None or not "":
                self.custom_objects.get_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    plural="applications",
                    namespace="argocd",
                    name=obj.metadata.name,
                )
            return None
        
        except ApiException:
            pass
        
        return None


class LonghornHelper:
    """Helper for Longhorn operations"""
    
    def __init__(self, k8s_helper: KubernetesHelper):
        self.k8s = k8s_helper
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_longhorn_volumes(self) -> List[Dict[str, Any]]:
        """Get all Longhorn volumes"""
        try:
            volumes = self.k8s.custom_objects.list_cluster_custom_object(
                group="longhorn.io",
                version="v1beta2", 
                plural="volumes"
            )
            return volumes.get("items", [])
        except ApiException as e:
            logger.error(f"Failed to get Longhorn volumes: {e}")
            return []
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=30))
    def detach_volume(self, volume_name: str, dry_run: bool = False) -> bool:
        """Detach a Longhorn volume"""
        if dry_run:
            logger.info(f"[DRY-RUN] Would detach Longhorn volume: {volume_name}")
            return True
        
        try:
            # Get current volume
            volume = self.k8s.custom_objects.get_namespaced_custom_object(group="longhorn.io",version="v1beta2",
                                                                          namespace="longhorn",
                                                                          name=volume_name,plural="volumes")
            
            # Check if already detached
            if volume.get("status", {}).get("state") == "detached":
                logger.info(f"Volume {volume_name} already detached")
                return True
            
            # Request detach by clearing nodeID
            volume["spec"]["nodeID"] = ""
            
            self.k8s.custom_objects.patch_namespaced_custom_object(
                group="longhorn.io",
                version="v1beta2", 
                plural="volumes",
                name=volume_name,
                namespace="longhorn",
                body=volume
            )
            
            logger.info(f"Detach requested for volume: {volume_name}")
            return True
            
        except ApiException as e:
            logger.error(f"Failed to detach volume {volume_name}: {e}")
            return False
    
    def wait_for_detachment(self, volume_names: List[str], timeout: int = 300) -> bool:
        """Wait for all volumes to be detached"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_detached = True
            
            for volume_name in volume_names:
                try:
                    volume = self.k8s.custom_objects.get_cluster_custom_object(
                        group="longhorn.io",
                        version="v1beta2",
                        plural="volumes", 
                        name=volume_name
                    )
                    
                    state = volume.get("status", {}).get("state", "unknown")
                    if state != "detached":
                        all_detached = False
                        logger.info(f"Volume {volume_name} state: {state}")
                        break
                        
                except ApiException as e:
                    logger.warning(f"Failed to check volume {volume_name}: {e}")
                    all_detached = False
                    break
            
            if all_detached:
                logger.info("All volumes detached successfully")
                return True
            
            time.sleep(10)
        
        logger.error(f"Timeout waiting for volume detachment after {timeout}s")
        return False


class ArgoHelper:
    """Helper for Argo CD operations"""

    def __init__(self, k8s_helper: KubernetesHelper):
        self.k8s = k8s_helper
        self.has_argo = self._check_argo_availability()

    def _check_argo_availability(self) -> bool:
        """Check if Argo CD CRDs are available"""
        try:
            self.k8s.custom_objects.list_cluster_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="applications"
            )
            return True
        except ApiException:
            return False

    def get_all_applications(self) -> List[Dict[str, Any]]:
        """Get all Argo CD applications"""
        if not self.has_argo:
            return []

        try:
            response = self.k8s.custom_objects.list_cluster_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="applications"
            )
            return response.get("items", [])
        except ApiException as e:
            logger.error(f"Failed to list Argo applications: {e}")
            return []

    def disable_self_heal(self, app_name: str, namespace: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Disable selfHeal for a specific Argo application
        Returns the original selfHeal setting for restoration
        """
        if not self.has_argo:
            return {}
        try:
            # Get current application
            app = self.k8s.custom_objects.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name
            )
            # Extract current selfHeal setting
            sync_policy = app.get("spec", {}).get("syncPolicy", {})
            automated = sync_policy.get("automated", {})
            original_self_heal = automated.get("selfHeal", False)
            logger.info(f"Application {app_name} current selfHeal: {original_self_heal}")
            if dry_run:
                logger.info(f"[DRY RUN] Would disable selfHeal for application {app_name}")
                return {"selfHeal": original_self_heal}

            # Only update if selfHeal is currently enabled
            if original_self_heal:
                # Ensure nested structure exists
                if "spec" not in app:
                    app["spec"] = {}
                if "syncPolicy" not in app["spec"]:
                    app["spec"]["syncPolicy"] = {}
                if "automated" not in app["spec"]["syncPolicy"]:
                    app["spec"]["syncPolicy"]["automated"] = {}

                # Disable selfHeal
                app["spec"]["syncPolicy"]["automated"] = None
                # Update the application
                self.k8s.custom_objects.patch_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="applications",
                    name=app_name,
                    body=app
                )
                logger.info(f"Disabled selfHeal for application {app_name}")
            return {"selfHeal": original_self_heal}
        except ApiException as e:
            logger.error(f"Failed to disable selfHeal for application {app_name}: {e}")
            return {}


    def restore_self_heal(self, app_name: str, namespace: str, original_setting: Dict[str, Any],
                          dry_run: bool = False) -> bool:
        """Restore original selfHeal setting for an Argo application"""
        if not self.has_argo or not original_setting:
            return True

        original_self_heal = original_setting.get("selfHeal", False)

        if dry_run:
            logger.info(f"[DRY RUN] Would restore selfHeal={original_self_heal} for application {app_name}")
            return True

        try:
            # Get current application
            app = self.k8s.custom_objects.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name
            )

            # Restore original selfHeal setting
            if "spec" not in app:
                app["spec"] = {}
            if "syncPolicy" not in app["spec"]:
                app["spec"]["syncPolicy"] = {}
            if "automated" not in app["spec"]["syncPolicy"]:
                app["spec"]["syncPolicy"]["automated"] = {}

            app["spec"]["syncPolicy"]["automated"]["selfHeal"] = original_self_heal

            # Update the application
            self.k8s.custom_objects.patch_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
                body=app
            )

            logger.info(f"Restored selfHeal={original_self_heal} for application {app_name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to restore selfHeal for application {app_name}: {e}")
            return False


class NodeDrainer:
    """Main orchestrator for node draining operations"""
    
    def __init__(self):
        self.k8s = KubernetesHelper()
        self.longhorn = LonghornHelper(self.k8s)
        self.argo = ArgoHelper(self.k8s)
        self.checkpoint_file = Path("drain_checkpoint.json")
    
    def save_checkpoint(self, checkpoint: CheckpointData):
        """Save checkpoint to file"""
        with open(self.checkpoint_file, 'w') as f:
            json.dump(asdict(checkpoint), f, indent=2, default=str)
        logger.info(f"Checkpoint saved to {self.checkpoint_file}")
    
    def load_checkpoint(self) -> Optional[CheckpointData]:
        """Load checkpoint from file"""
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
            return CheckpointData(**data)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def preflight_checks(self) -> bool:
        """Perform preflight verification"""
        logger.info("Starting preflight checks...")
        
        # Verify permissions
        if not self.k8s.verify_permissions():
            logger.error("Insufficient permissions - cluster-admin required")
            return False
        
        # Check nodes are ready
        nodes = self.k8s.get_nodes()
        for node in nodes:
            for condition in node.status.conditions:
                if condition.type == "Ready" and condition.status != "True":
                    logger.error(f"Node {node.metadata.name} is not Ready")
                    return False
        
        logger.info("Preflight checks passed")
        return True
    
    def discover_pvc_workloads(self) -> Dict[str, Dict[str, Any]]:
        """Discover workloads using PVCs"""
        logger.info("Discovering PVC-related workloads...")
        return self.k8s.get_pvcs_and_pods()

    def quiesce_workloads(self, dry_run: bool = False) -> Dict[str, Dict[str, Any]]:
        """Scale down workloads and disable Argo CD selfHeal for all applications"""
        original_settings = {}
        pvc_mapping = self.k8s.get_pvcs_and_pods()
        # Collect all unique controllers
        controllers = set()
        for pvc_data in pvc_mapping.values():
            controllers.update(pvc_data["controllers"])

        logger.info(f"Found {len(controllers)} controllers to quiesce: {controllers}")

        # Handle Argo CD applications - disable selfHeal for ALL applications
        if self.argo.has_argo:
            logger.info("Disabling selfHeal for all Argo CD applications")
            applications = self.argo.get_all_applications()

            for app in applications:
                app_name = app["metadata"]["name"]
                app_namespace = app["metadata"]["namespace"]

                original_setting = self.argo.disable_self_heal(
                    app_name, app_namespace, dry_run=dry_run
                )

                if original_setting:
                    original_settings[f"argo_app_{app_namespace}_{app_name}"] = {
                        "type": "argo_self_heal",
                        "namespace": app_namespace,
                        "name": app_name,
                        "settings": original_setting
                    }
        # Scale down controllers
        for controller_str in controllers:
            kind, namespace, name = controller_str.split("/", 2)
            # Scale down the controller
            original_settings[controller_str] = {
                "type": "controller_scale",
                "settings": self._scale_controller(kind, namespace, name, dry_run)
            }
        return original_settings
    
    def _scale_controller(self, kind: str, namespace: str, name: str, 
                         dry_run: bool = False) -> Dict[str, Any]:
        """Scale down a specific controller"""
        original = {}
        
        try:
            if kind == "Deployment":
                if dry_run:
                    logger.info(f"[DRY-RUN] Would scale down Deployment {namespace}/{name}")
                    return {"replicas": 1}  # Mock original
                
                deploy = self.k8s.apps_v1.read_namespaced_deployment(name, namespace)
                original["replicas"] = deploy.spec.replicas
                
                deploy.spec.replicas = 0
                self.k8s.apps_v1.patch_namespaced_deployment(name, namespace, deploy)
                
            elif kind == "StatefulSet":
                if dry_run:
                    logger.info(f"[DRY-RUN] Would scale down StatefulSet {namespace}/{name}")
                    return {"replicas": 1}
                
                sts = self.k8s.apps_v1.read_namespaced_stateful_set(name, namespace)
                original["replicas"] = sts.spec.replicas
                
                sts.spec.replicas = 0
                self.k8s.apps_v1.patch_namespaced_stateful_set(name, namespace, sts)
                
            elif kind == "CronJob":
                if dry_run:
                    logger.info(f"[DRY-RUN] Would suspend CronJob {namespace}/{name}")
                    return {"suspend": False}
                
                cj = self.k8s.batch_v1.read_namespaced_cron_job(name, namespace)
                original["suspend"] = cj.spec.suspend
                
                cj.spec.suspend = True
                self.k8s.batch_v1.patch_namespaced_cron_job(name, namespace, cj)
                
            logger.info(f"Scaled down {kind} {namespace}/{name}")
            
        except ApiException as e:
            logger.error(f"Failed to scale {kind} {namespace}/{name}: {e}")
        
        return original
    
    def wait_for_pod_termination(self, pvc_mapping: Dict[str, Dict[str, Any]], 
                               timeout: int = 300) -> bool:
        """Wait for pods to terminate after scaling down"""
        logger.info("Waiting for pods to terminate...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            active_pods = []
            
            for pvc_data in pvc_mapping.values():
                for pod in pvc_data["pods"]:
                    try:
                        current_pod = self.k8s.core_v1.read_namespaced_pod(
                            pod.metadata.name, pod.metadata.namespace
                        )
                        if current_pod.status.phase in ["Running", "Pending"]:
                            active_pods.append(f"{pod.metadata.namespace}/{pod.metadata.name}")
                    except ApiException:
                        # Pod likely deleted
                        pass
            
            if not active_pods:
                logger.info("All pods terminated")
                return True
            
            logger.info(f"Waiting for {len(active_pods)} pods to terminate")
            time.sleep(10)
        
        logger.error(f"Timeout waiting for pod termination after {timeout}s")
        return False
    
    def detach_longhorn_volumes(self, dry_run: bool = False) -> bool:
        """Detach all Longhorn volumes"""
        logger.info("Detaching Longhorn volumes...")
        
        volumes = self.longhorn.get_longhorn_volumes()
        attached_volumes = []
        
        for volume in volumes:
            state = volume.get("status", {}).get("state", "unknown")
            if state == "attached":
                attached_volumes.append(volume["metadata"]["name"])
        
        if not attached_volumes:
            logger.info("No attached volumes found")
            return True
        
        logger.info(f"Found {len(attached_volumes)} attached volumes")
        
        # Detach volumes in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.longhorn.detach_volume, vol_name, dry_run): vol_name
                for vol_name in attached_volumes
            }
            
            for future in as_completed(futures):
                vol_name = futures[future]
                try:
                    if not future.result():
                        logger.error(f"Failed to detach volume {vol_name}")
                        return False
                except Exception as e:
                    logger.error(f"Exception detaching volume {vol_name}: {e}")
                    return False
        
        if dry_run:
            return True
        
        # Wait for detachment
        return self.longhorn.wait_for_detachment(attached_volumes)
    
    def drain_nodes(self, node_selector: Optional[str] = None, 
                   force_evict_pdb: bool = False, dry_run: bool = False) -> bool:
        """Drain all nodes"""
        logger.info("Starting node drain...")
        
        nodes = self.k8s.get_nodes(node_selector)
        if not nodes:
            logger.warning("No nodes found to drain")
            return True
        
        logger.info(f"Draining {len(nodes)} nodes")
        
        # Separate control plane and worker nodes
        control_plane_nodes = []
        worker_nodes = []
        
        for node in nodes:
            labels = node.metadata.labels or {}
            if ("node-role.kubernetes.io/control-plane" in labels or
                "node-role.kubernetes.io/master" in labels):
                control_plane_nodes.append(node)
            else:
                worker_nodes.append(node)
        
        # Drain workers first, then control plane
        all_nodes = worker_nodes + control_plane_nodes
        
        for node in all_nodes:
            if not self._drain_single_node(node.metadata.name, force_evict_pdb, dry_run):
                return False
        
        logger.info("All nodes drained successfully")
        return True
    
    def _drain_single_node(self, node_name: str, force_evict_pdb: bool = False, 
                          dry_run: bool = False) -> bool:
        """Drain a single node"""
        if dry_run:
            logger.info(f"[DRY-RUN] Would drain node: {node_name}")
            return True
        
        try:
            # Cordon the node first
            logger.info(f"Cordoning node: {node_name}")
            node = self.k8s.core_v1.read_node(node_name)
            node.spec.unschedulable = True
            self.k8s.core_v1.patch_node(node_name, node)
            
            # Get pods on this node (excluding DaemonSet pods)
            pods = self.k8s.core_v1.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            )
            
            pods_to_evict = []
            for pod in pods.items:
                # Skip DaemonSet pods, completed pods
                if (pod.metadata.owner_references and
                    any(ref.kind == "DaemonSet" for ref in pod.metadata.owner_references)):
                    continue
                
                if pod.status.phase in ["Succeeded", "Failed"]:
                    continue
                
                pods_to_evict.append(pod)
            
            if not pods_to_evict:
                logger.info(f"No pods to evict from node: {node_name}")
                return True
            
            logger.info(f"Evicting {len(pods_to_evict)} pods from node: {node_name}")
            
            # Evict pods
            for pod in pods_to_evict:
                try:
                    eviction = client.V1Eviction(
                        metadata=client.V1ObjectMeta(
                            name=pod.metadata.name,
                            namespace=pod.metadata.namespace
                        )
                    )
                    
                    self.k8s.core_v1.create_namespaced_pod_eviction(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                        body=eviction
                    )
                    
                except ApiException as e:
                    if e.status == 429:  # Too Many Requests (PodDisruptionBudget)
                        if force_evict_pdb:
                            logger.warning(f"Force deleting pod {pod.metadata.name} due to PDB")
                            self.k8s.core_v1.delete_namespaced_pod(
                                pod.metadata.name, pod.metadata.namespace,
                                grace_period_seconds=0
                            )
                        else:
                            logger.error(f"Pod eviction blocked by PDB: {pod.metadata.name}")
                            return False
                    else:
                        logger.error(f"Failed to evict pod {pod.metadata.name}: {e}")
                        return False
            
            # Wait for pods to be evicted
            timeout = 300
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                remaining_pods = self.k8s.core_v1.list_pod_for_all_namespaces(
                    field_selector=f"spec.nodeName={node_name}"
                )
                
                non_ds_pods = [
                    pod for pod in remaining_pods.items
                    if not (pod.metadata.owner_references and
                           any(ref.kind == "DaemonSet" for ref in pod.metadata.owner_references))
                    and pod.status.phase not in ["Succeeded", "Failed"]
                ]
                
                if not non_ds_pods:
                    logger.info(f"Node {node_name} drained successfully")
                    return True
                
                logger.info(f"Waiting for {len(non_ds_pods)} pods to be evicted from {node_name}")
                time.sleep(10)
            
            logger.error(f"Timeout draining node {node_name}")
            return False
            
        except ApiException as e:
            logger.error(f"Failed to drain node {node_name}: {e}")
            return False
    
    def generate_report(self, checkpoint: CheckpointData) -> Dict[str, Any]:
        """Generate final report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "operation": "node_drain",
            "status": "completed",
            "summary": {
                "nodes_processed": len(checkpoint.nodes),
                "pvcs_discovered": len(checkpoint.pvc_workload_mapping),
                "controllers_scaled": len(checkpoint.original_replicas),
                "argo_apps_modified": len(checkpoint.original_argo_policies),
                "longhorn_volumes": len(checkpoint.longhorn_volumes)
            },
            "checkpoint_file": str(self.checkpoint_file)
        }
        
        return report 