#!/bin/bash

# Usage: ./setup-nat.sh <source_ip_or_subnet>
# Example: ./setup-nat.sh 192.168.99.0/24

SRC_IP="$1"

if [ -z "$SRC_IP" ]; then
  echo "Usage: $0 <source_ip_or_subnet>"
  exit 1
fi

# Add NAT table
nft add table ip nat

# Add postrouting chain
nft add chain ip nat postrouting { type nat hook postrouting priority 100 \; }

# Add MASQUERADE rule for the given source IP
nft add rule ip nat postrouting ip saddr $SRC_IP oif "vmbr0" masquerade

# Save ruleset
nft list ruleset > /etc/nftables.conf

echo "NAT setup complete for source IP: $SRC_IP"