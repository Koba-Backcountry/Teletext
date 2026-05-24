#!/bin/bash
set -e

terraform init
terraform apply -auto-approve

IP=$(terraform output -raw ec2_public_ip)
echo "EC2 public IP: $IP"

cat <<EOF > hosts.ini
[ec2]
$IP ansible_user=ubuntu ansible_ssh_private_key_file=./MyKeyPair.pem
EOF

ansible-playbook -i hosts.ini deploy-site.yml

echo "OPEN: http://$IP"
