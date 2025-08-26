# ⭐ Favorite Setting: Allowlist a Single LAN IP to Access a Docker Bridge (iptables) + Static Route

> **Goal (not a bug):** Keep Docker’s default bridge isolation **on**, but allow **only my workstation** to reach containers directly by IP on a user-defined Docker bridge. This documents the setup for reuse, including the **required static route** on the LAN PC or home router.

---

## STAR Summary

### **Situation**
- Host: Linux/Proxmox box running Docker with a user-defined bridge network (e.g., `runtime-network` → `192.168.30.0/24`).
- Default Docker chains in the **filter** table enforce bridge isolation (e.g., drops on `FORWARD` to `br-…` from non-bridge interfaces).
- I want **direct IP access** from exactly one LAN IP (my workstation: `192.168.1.2`) to the containers on that bridge **without** opening it to the entire LAN.
- **Routing requirement:** The workstation (or the home router for the whole LAN) must know that the path to `192.168.30.0/24` goes **via the Docker host** (e.g., `192.168.1.121`). This is a *route*, not NAT.

### **Task**
- Implement a **least-privilege** allow that:
  - Works with Docker’s chain layout (uses **DOCKER-USER** where Docker won’t overwrite).
  - Survives early raw-table drops if present.
  - Is **idempotent** via Ansible.
  - Keeps isolation for anyone else on the LAN.
  - Ensures **routing** to the Docker subnet by adding a **static route** on the LAN PC or the home router.

### **Action**
Below uses the Ansible `ansible.builtin.iptables` module. Tweak the variables to your environment.

```yaml
# playbook excerpt
# file: docker-allowlist.yml
- hosts: docker_host
  become: true
  vars:
    lan_ip: "192.168.1.2/32"          # the only allowed source (your workstation)
    docker_subnet: "192.168.30.0/24"  # user-defined bridge subnet (runtime-network)
    docker_host_lan_ip: "192.168.1.121"               # LAN IP of the Docker host (gateway for the route)
    lan_iface: "{{ ansible_default_ipv4.interface }}" # or set explicitly: "eno1" / "eth0"

  tasks:
    - name: Ensure return traffic is allowed (baseline)
      ansible.builtin.iptables:
        table: filter
        chain: FORWARD
        ctstate: ESTABLISHED,RELATED
        jump: ACCEPT
        state: present
        action: insert
        rule_num: 1

    - name: Allow NEW from my LAN IP to Docker subnet via DOCKER-USER
      ansible.builtin.iptables:
        table: filter
        chain: DOCKER-USER
        in_interface: "{{ lan_iface }}"
        source: "{{ lan_ip }}"
        destination: "{{ docker_subnet }}"
        ctstate: NEW
        jump: ACCEPT
        state: present
        action: insert
        rule_num: 1   # ensure it runs before Docker’s own jumps

    - name: Bypass early raw drops (if any) for my LAN IP → Docker subnet
      ansible.builtin.iptables:
        table: raw
        chain: PREROUTING
        in_interface: "{{ lan_iface }}"
        source: "{{ lan_ip }}"
        destination: "{{ docker_subnet }}"
        jump: ACCEPT
        state: present
        action: insert
        rule_num: 1
```

> **Important:** No SNAT is needed for `192.168.1.0/24 ↔ 192.168.30.0/24` intra‑LAN access. This is **pure routed** traffic. Docker’s own NAT (in `nat/POSTROUTING`) remains for container → Internet.

---

## Add the Static Route (PC or Router)

You must tell the **sender** where to find `192.168.30.0/24`. Choose **one**:

### Option A — Add route on **your workstation** (fastest)
- **Windows (PowerShell or cmd):**
  ```bat
  REM Persistent static route: 192.168.30.0/24 via 192.168.1.121
  route -p ADD 192.168.30.0 MASK 255.255.255.0 192.168.1.121 METRIC 1
  REM Remove if needed:
  route DELETE 192.168.30.0
  ```

- **Linux:**
  ```bash
  # One-shot (non-persistent)
  sudo ip route add 192.168.30.0/24 via 192.168.1.121

  # NetworkManager persistent (replace <conn> with your connection name)
  nmcli connection show
  sudo nmcli connection modify "<conn>" +ipv4.routes "192.168.30.0/24 192.168.1.121"
  sudo nmcli connection up "<conn>"
  ```

- **macOS:**
  ```bash
  # One-shot (not persistent across reboot)
  sudo route -n add 192.168.30.0/24 192.168.1.121

  # Persistence requires a launchd script or a network change hook (optional).
  ```

### Option B — Add route on the **home router** (recommended if you want any LAN host to reach containers)
- **OpenWrt (SSH/CLI):**
  ```bash
  uci add network route
  uci set network.@route[-1].interface='lan'
  uci set network.@route[-1].target='192.168.30.0'
  uci set network.@route[-1].netmask='255.255.255.0'
  uci set network.@route[-1].gateway='192.168.1.121'
  uci commit network
  /etc/init.d/network reload
  ```
  *(LuCI UI → Network → Static Routes → Add: Target `192.168.30.0/24`, Gateway `192.168.1.121`, Interface `lan`)*

- **pfSense/OPNsense:**
  - **System → Routing → Static Routes → Add**
    - **Network:** `192.168.30.0/24`
    - **Gateway:** create/select a gateway pointing to `192.168.1.121` on the LAN
    - Save & Apply

- **Generic consumer router (ASUS/MikroTik/TP-Link/Netgear):**
  - Look for **Advanced → Routing → Static Route**.
  - **Destination:** `192.168.30.0` **Mask:** `255.255.255.0` **Gateway:** `192.168.1.121` **Interface:** LAN.

> After setting the route, ensure the **Docker host firewall** (above) permits the traffic; return path is handled by the `ESTABLISHED,RELATED` rule.

---

## Verification Steps

1) **From the workstation, confirm the route**
```bash
# Linux
ip route get 192.168.30.10

# Windows
tracert 192.168.30.10

# macOS
traceroute 192.168.30.10
```
The **next hop** should be `192.168.1.121` (Docker host).

2) **Counters increment on ACCEPT rules (Docker host)**
```bash
sudo iptables -t filter -L DOCKER-USER -n -v --line-numbers
sudo iptables -t raw    -L PREROUTING  -n -v --line-numbers
ping -c3 192.168.30.10  # from the workstation
# Re-check counters ↑ for increments on your ACCEPT rules
```

3) **Functional check**
```bash
ping -c3 192.168.30.10
curl -sS http://192.168.30.10:8080/ | head
```

---

## Result
![ip_result]("./docs/container_access_ok_result.png")

## Persistence

Changes via `ansible.builtin.iptables` are ephemeral. Either re-apply via Ansible at boot, or save with iptables-persistent:

```bash
sudo apt-get update && sudo apt-get install -y iptables-persistent netfilter-persistent
sudo netfilter-persistent save   # saves to /etc/iptables/rules.v4
```

For **persistent routes** on PCs:
- Windows uses `route -p` (already shown).
- Linux: use NetworkManager (`nmcli`), netplan, or distro-specific network config.
- macOS: use launchd or a startup script to re-add the route.

---

## Rollback (Ansible)

Remove just the two allow rules (match the same specs you inserted):

```yaml
- hosts: docker_host
  become: true
  vars:
    lan_ip: "192.168.1.2/32"
    docker_subnet: "192.168.30.0/24"
    lan_iface: "{{ ansible_default_ipv4.interface }}"

  tasks:
    - name: Remove DOCKER-USER allow
      ansible.builtin.iptables:
        table: filter
        chain: DOCKER-USER
        in_interface: "{{ lan_iface }}"
        source: "{{ lan_ip }}"
        destination: "{{ docker_subnet }}"
        ctstate: NEW
        jump: ACCEPT
        state: absent

    - name: Remove raw PREROUTING allow
      ansible.builtin.iptables:
        table: raw
        chain: PREROUTING
        in_interface: "{{ lan_iface }}"
        source: "{{ lan_ip }}"
        destination: "{{ docker_subnet }}"
        jump: ACCEPT
        state: absent
```

> If you added the baseline `FORWARD` rule and want it gone too, remove with `state: absent` and the same parameters.

---

## Notes & Variants

- **Interface name**: if your primary NIC isn’t what Ansible detects, set `lan_iface` explicitly (`eno1`, `eth0`, etc.).
- **Multiple bridges**: replicate the DOCKER-USER and raw rules for each Docker subnet you want reachable.
- **Published ports** (`-p host:container`): they use DNAT in `nat/DOCKER` and don’t need direct bridge access, but your allowlist still works fine.
- **Why DOCKER-USER?** Docker won’t overwrite this chain; it’s the intended place for admin policy.
- **Why raw/PREROUTING?** It guarantees your allow survives any early raw-table drops/NOTRACK before conntrack/NAT/filter.
- **Why a static route?** Without it, your PC (or LAN) will try to reach `192.168.30.0/24` via the default gateway, which doesn’t know that subnet; the traffic never reaches the Docker host for forwarding.