#!/bin/bash
source <(curl -fsSL https://raw.githubusercontent.com/ngodat0103/common-stuff/refs/heads/main/0-shell/7-log/log.sh)
# pre-shutdown task, make sure to scaled pod having LongHorn volume and make sure volume is detach

source <(curl -fsSL https://raw.githubusercontent.com/ngodat0103/common-stuff/refs/heads/main/0-shell/8-longhorn/pre-shutdown-longhorn.sh)
pre-shutdown-longhorn

vagrant halt && print_info "All machined all stoped succesfully" || print_error "Stop instances failed:"