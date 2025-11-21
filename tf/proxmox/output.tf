output "lxc_default" {
  value     = module.lxc_production
  sensitive = true
}
output "k8s-masters" {
  value = module.k8s_masters
}
output "k8s-workers" {
  value = module.k8s_workers
}
output "duc_vm" {
  value = module.duc-vm
}
