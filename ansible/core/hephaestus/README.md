# Hephaestus – Ansible Bootstrap (Build/CI Node)

This playbook installs a full development toolchain and CI runners on a Debian/Ubuntu host:

- Core packages & QoL tools
- Go (from official tarball)
- Apache Maven (from official tarball)
- Docker Engine + Compose plugin (from Docker repo)
- Kubernetes tools: kubectl (+ optional Helm, k9s)
- GitHub Actions runner (systemd-managed, optional registration)
- GitLab Runner (package install, optional registration)

## Quick Start

1. Edit inventory and variables:
   - `inventory.ini`: set `ansible_host` and `ansible_user`
   - `group_vars/hephaestus.yml`: set versions and tokens (GitHub/GitLab) as needed

2. Run:
   ```bash
   ansible-playbook -i inventory.ini site.yml
   ```

### Passing sensitive tokens at runtime (recommended)
```bash
ansible-playbook -i inventory.ini site.yml \      -e github_runner_token="$GITHUB_RUNNER_TOKEN" \      -e gitlab_runner_registration_token="$GITLAB_REG_TOKEN"
```

## Notes

- GitHub Actions runner registration only runs if `github_runner_token` is set (non-empty).
- GitLab Runner registration only runs if `gitlab_runner_registration_token` is set.
- Helm and k9s install steps are included; set explicit versions if you need pinning.
