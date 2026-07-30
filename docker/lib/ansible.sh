# Shared Ansible logic — inventory generation + playbook execution

ansible_generate_inventory() {
  local provider=$1
  local template="docker/ansible/inventory.${provider}.j2"
  local out="docker/ansible/inventory.ini"

  if [ ! -f "$template" ]; then
    echo "ERROR: inventory template not found: $template"
    exit 1
  fi

  sed -e "s/{{ user }}/$(whoami)/g" \
      -e "s|{{ repo_path }}|$REPO_DIR|g" \
      "$template" > "$out"
  echo "  Inventory: $out"
}

ansible_generate_inventory_base() {
  local provider=${1:-lxd}
  local template="docker/ansible/inventory.${provider}.base.j2"
  local out="docker/ansible/inventory.ini"

  if [ ! -f "$template" ]; then
    echo "ERROR: base inventory template not found: $template"
    exit 1
  fi

  sed -e "s/{{ user }}/$(whoami)/g" \
      -e "s|{{ repo_path }}|$REPO_DIR|g" \
      "$template" > "$out"
  echo "  Inventory (base): $out"
}

ansible_run() {
  local playbook=$1
  local inventory="docker/ansible/inventory.ini"
  local wpath
  wpath="$REPO_DIR/$(ls "$WHEEL_DIR"/hierachain-*.whl 2>/dev/null | head -1)"
  local extra="provider=${PROVIDER} repo_path=${REPO_DIR} wheel_path=${wpath} user=$(whoami) ipfs_encryption_key=${IPFS_ENCRYPTION_KEY} explorer_token=${EXPLORER_TOKEN} dns_suffix=${DNS_SUFFIX}"

  echo "  Running playbook: $playbook"
  ansible-playbook -i "$inventory" "$playbook" --extra-vars "$extra"
}
