#!/bin/bash

export NAME="discord.eternal-engine.service"
export V_EXEC="$(pwd)/run.sh"
export V_USER="$(whoami)"
export V_DIR="$(pwd)"
export V_DESC="The Eternal Engine"

(envsubst < template.unit) > "$NAME"

sudo cp "$NAME" /etc/systemd/system

sudo systemctl daemon-reload

sudo systemctl enable "$name"