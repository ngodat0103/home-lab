# 🔍 Verifying Ansible Variables from CLI

When working with **group_vars**, it’s often useful to confirm how Ansible actually sees your variables *before* running a playbook. This helps avoid undefined-variable errors or mis-configured values at runtime.

---

## 1. Print a Single Variable
Use the `debug` module in ad-hoc mode:

```bash
ansible all -i inventory.ini -m debug -a "var=kube_vip_interface"
```

Example output:
```
ok: [node1] => {
    "kube_vip_interface": "eth0"
}
```

- `all` = target host/group (can also be `k8s` or a single host).
- If the variable is **undefined**, Ansible will throw an error.

---

## 2. Print Multiple Variables
```bash
ansible all -i inventory.ini -m debug -a "msg='{{ kube_vip_enabled }} {{ kube_vip_address }}'"
```

Output shows the concatenated values:
```
ok: [node1] => {
    "msg": "true 192.168.1.135"
}
```

---

## 3. Verify Existence Only
If you only care whether a var exists:

```bash
ansible all -i inventory.ini -m assert -a 'that="kube_vip_address is defined"'
```

If missing:
```
fatal: [node1]: FAILED! => {"msg": "Assertion failed: kube_vip_address is defined"}
```

---

## 4. Dump All Variables
To see *everything* Ansible has loaded for a host:

```bash
ansible all -i inventory.ini -m setup    # facts + vars
ansible all -i inventory.ini -m debug -a "var=vars"   # all variables
```

⚠️ Warning: This can be very verbose and include secrets.

---

## 5. Inspect Inventory and group_vars Directly
```bash
ansible-inventory -i inventory.ini --list
ansible-inventory -i inventory.ini --host node1
```

This shows how Ansible merges inventory + group_vars + host_vars.

---

## ✅ Use Case: kube-vip Variables
Before applying playbooks, confirm the critical variables exist and look correct:

```bash
ansible all -i inventory.ini -m debug -a "var=kube_vip_enabled"
ansible all -i inventory.ini -m debug -a "var=kube_vip_arp_enabled"
ansible all -i inventory.ini -m debug -a "var=kube_proxy_strict_arp"
ansible all -i inventory.ini -m debug -a "var=kube_vip_controlplane_enabled"
ansible all -i inventory.ini -m debug -a "var=kube_vip_address"
ansible all -i inventory.ini -m debug -a "var=kube_vip_interface"
ansible all -i inventory.ini -m debug -a "var=supplementary_addresses_in_ssl_keys"
```

---

🔑 **Tip**: Add a small `make verify-vars` target in your repo to wrap these commands, so you can quickly check your `group_vars` before running any playbook.