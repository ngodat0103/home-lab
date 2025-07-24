#!/bin/bash

# pre-shutdown task, make sure to scaled pod having LongHorn volume and make sure volume is detach
./task-before-shutdown-longhorn.sh
vagrant halt