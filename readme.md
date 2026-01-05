> *"Move fast and break things"* — Mark Zuckerberg  
> *"I moved fast. Things are broken."* — Me, at 3 AM

Welcome to **dev-oops** — my personal laboratory where I cosplay as a DevOps engineer, break production systems that serve exactly one user (me), and learn enterprise patterns the hard way: by experiencing every possible failure mode firsthand.

This is what happens when you have more hardware than common sense.

---

## What is This?

This repository contains **enterprise-grade infrastructure** for a **hobbyist-grade homelab**. It's over-engineered, over-documented, and occasionally over-heated.

I treat my homelab like a Fortune 500 company's infrastructure, except:
- My SLA is "probably up"
- My incident response is "wake up and panic"
- My disaster recovery plan is "cry, then restore from backup"
- My change management process is `git push --force` and pray

---

## The Victim (Hardware Specs)

| Component | Spec | Notes |
|-----------|------|-------|
| **CPU** | 56 x Intel Xeon E5-2680 v4 @ 2.40GHz | Two sockets of raw, slightly-aged power |
| **RAM** | 62GB | Enough to run Kubernetes. Barely. |
| **Boot Mode** | Legacy BIOS | *"We don't do UEFI here"* |
| **Hypervisor** | Proxmox VE 9.0.3 | The backbone of my chaos |
| **Kernel** | Linux 6.14.8-2-pve | Latest and greatest (until tomorrow) |

### Storage Situation

```
┌─────────────┬─────────┬──────────────────────────────────┐
│ Device      │ Size    │ Purpose                          │
├─────────────┼─────────┼──────────────────────────────────┤
│ sda         │ 465.8G  │ Spinning rust from 2014          │
│ sdb         │ 931.5G  │ More spinning rust               │
│ nvme0n1     │ 1.8T    │ The fast boi (VMs live here)     │
└─────────────┴─────────┴──────────────────────────────────┘
```

---

## Architecture (a.k.a. "The Overkill")

```
                    ┌──────────────────────────────────────────────────┐
                    │                   THE INTERNET                    │
                    │              (where the danger lives)             │
                    └───────────────────────┬──────────────────────────┘
                                            │
                                            ▼
                    ┌──────────────────────────────────────────────────┐
                    │                   CLOUDFLARE                      │
                    │    DNS, Firewall, "Please don't DDoS me" layer   │
                    │              (Managed by Terraform)               │
                    └───────────────────────┬──────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PROXMOX VE                                      │
│                    (The hypervisor that runs everything)                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         KUBERNETES CLUSTER                           │    │
│  │                     (Deployed via Kubespray)                        │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │   Master    │  │   Worker    │  │   Worker    │                  │    │
│  │  │   Node(s)   │  │   Node 1    │  │   Node 2    │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  │         │                │                │                         │    │
│  │         └────────────────┼────────────────┘                         │    │
│  │                          ▼                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                        ARGOCD                                │   │    │
│  │  │           "GitOps: Because YOLO deploys are scary"          │   │    │
│  │  │                                                              │   │    │
│  │  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │    │
│  │  │   │ Traefik  │ │PostgreSQL│ │Vaultwarden│ │qBittorrent│      │   │    │
│  │  │   │ Ingress  │ │    DB    │ │ Passwords │ │ "Linux   │      │   │    │
│  │  │   │          │ │          │ │           │ │  ISOs"   │      │   │    │
│  │  │   └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     DOCKER VMs (The OG Setup)                       │    │
│  │                                                                      │    │
│  │   GitLab │ Jellyfin │ Nextcloud │ Grafana │ Prometheus │ More...    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                           LXC CONTAINERS                            │    │
│  │                        PostgreSQL │ SonarQube                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
dev-oops/
├── ansible/                    # Configuration Management
│   ├── core/                   # Core playbooks for everything
│   │   ├── hephaestus/        # CI/CD runner bootstrap (named after the Greek god of craftsmanship)
│   │   ├── lxc/               # LXC container configs
│   │   ├── proxmox/           # Hypervisor management
│   │   ├── teleport/          # Zero-trust access (fancy SSH)
│   │   ├── ubuntu-server/     # VM provisioning & apps
│   │   └── vpn-server/        # OpenVPN setup
│   ├── kubernetes/            # Kubespray cluster deployment
│   └── sonarqube/             # Code quality (yes, I lint my YAML)
│
├── kubernetes/                 # K8s Manifests & ArgoCD
│   ├── argocd/                # GitOps all the things
│   │   ├── argocd-app/        # Application definitions
│   │   │   ├── daemon/        # DaemonSets (monitoring)
│   │   │   ├── stateful/      # PostgreSQL, Redis, etc.
│   │   │   └── stateless/     # Traefik, Vaultwarden
│   │   └── argocd-crd/        # ArgoCD itself (meta!)
│   └── traefik/               # Ingress controller
│
├── tf/                        # Terraform (Infrastructure as Code)
│   ├── cloudflare/            # DNS & Firewall rules
│   ├── proxmox/               # VM provisioning
│   ├── uptimerobot/           # "Is it down?" monitoring
│   └── terraform-module/      # Reusable modules
│
└── disaster-recovery/         # For when things go wrong (often)
    └── vaultwarden/           # Password backup (very important)
```

---

## The Stack of Chaos

### Infrastructure Layer
| Tool | Purpose | 
|------|---------|
| **Proxmox VE** | Hypervisor |
| **Terraform** | Infrastructure as Code |
| **Cloudflare** | DNS & Security |

### Configuration Management
| Tool | Purpose | Chaos Level |
|------|---------|-------------|
| **Ansible** | Server configuration | 🔥🔥 Medium (YAML indentation trauma) |
| **Kubespray** | K8s deployment | 🔥🔥🔥 High (so many variables) |

### Container Orchestration
| Tool | Purpose | Chaos Level |
|------|---------|-------------|
| **Kubernetes** | Container orchestration | 🔥🔥🔥🔥 Extreme (it's Kubernetes) |
| **ArgoCD** | GitOps deployment | 🔥🔥 Medium (sync loops haunt my dreams) |
| **Traefik** | Ingress & SSL | 🔥🔥 Medium (middleware inception) |
| **Longhorn** | Distributed storage | 🔥🔥🔥 High (distributed systems are fun!) |

### Observability (Watching Things Break)
| Tool | Purpose | Chaos Level |
|------|---------|-------------|
| **Prometheus** | Metrics collection | 🔥🔥 Medium |
| **Grafana** | Pretty dashboards | 🔥 Low (the fun part) |
| **Loki** | Log aggregation | 🔥🔥 Medium |
| **Alloy** | Telemetry collector | 🔥🔥 Medium |
| **UptimeRobot** | External monitoring | 🔥 Low (it texts me at 3 AM) |

### Applications (The Actual Useful Stuff)
| App | Purpose | Why |
|-----|---------|-----|
| **GitLab** | Git hosting & CI/CD | Self-hosted GitHub at home |
| **Vaultwarden** | Password manager | Because I can't remember anything |
| **Nextcloud** | File sync | Google Drive but with more RAM usage |
| **Jellyfin** | Media server | "Linux ISOs" streaming |
| **qBittorrent** | Torrent client | For "Linux ISOs" |
| **PostgreSQL** | Database | The elephant in the room |
| **Teleport** | Zero-trust access | SSH but fancier |

---

## Lessons Learned (The Hard Way)

### Things I've Broken (So Far)

- [x] Deleted production database (it was just my passwords, no big deal)
- [x] Ran `terraform destroy` on the wrong workspace
- [x] Forgot to backup before "quick fix"
- [x] Locked myself out of my own server
- [x] Filled up the boot disk with logs
- [x] Created an infinite ArgoCD sync loop
- [x] Misconfigured firewall, couldn't SSH in
- [ ] Lost data permanently (knock on wood 🪵)
---

## Contributing

This is my personal homelab, so contributions are... unexpected? But if you:

1. Found a security issue → Please tell me (nicely)
2. Have a suggestion → Open an issue
3. Want to judge my YAML → Fair enough

---

## License

This project is licensed under the **"Works On My Machine"** license.

You're free to:
- Copy this and break your own stuff
- Learn from my mistakes
- Laugh at my configuration choices