#!/bin/bash
# Vault 자동 Unseal 스크립트

echo "🔐 Vault Unseal 스크립트 시작..."

# Vault 상태 확인
VAULT_STATUS=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')

if [ "$VAULT_STATUS" = "true" ]; then
    echo "⚠️ Vault가 sealed 상태입니다. Unseal을 진행합니다..."
    
    # Unseal 키 파일 확인
    if [ -f "/data/terraform-proxmox/vault_unseal_keys.txt" ]; then
        echo "📋 저장된 Unseal 키를 사용합니다..."
        UNSEAL_KEY=$(cat /data/terraform-proxmox/vault_unseal_keys.txt)
        
        # Vault Unseal 실행
        docker exec vault-dev vault operator unseal "$UNSEAL_KEY"
        
        if [ $? -eq 0 ]; then
            echo "✅ Vault Unseal 성공"
        else
            echo "❌ Vault Unseal 실패"
            exit 1
        fi
    else
        echo "❌ Unseal 키 파일이 없습니다: /data/terraform-proxmox/vault_unseal_keys.txt"
        echo "Vault를 초기화하고 Unseal 키를 저장해야 합니다."
        exit 1
    fi
else
    echo "✅ Vault가 이미 unsealed 상태입니다."
fi

# 최종 상태 확인
echo "🔍 Vault 최종 상태 확인..."
docker exec vault-dev vault status
