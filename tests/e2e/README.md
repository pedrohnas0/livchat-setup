# 🧪 Testes E2E - Workflow de Monitoramento

## 🎯 Configuração Padrão do Servidor

**IMPORTANTE**: Todos os testes devem usar esta configuração:

```yaml
Servidor: e2e-complete-test
Tipo: CCX23 (4 vCPU AMD, 16GB RAM, 80GB NVMe)
OS: Debian 12
Região: ash (Ashburn, VA)
SSH Key: e2e-complete-test_key
Custo: €0.026/hora
```

## 🚀 Workflow de Execução com Monitoramento

### 1. Setup Inicial

```bash
# IMPORTANTE: SEMPRE usar ambiente virtual para testes
# Ativar ambiente virtual (OBRIGATÓRIO)
source venv/bin/activate

# Configurar credenciais (se necessário)
export HETZNER_TOKEN="seu-token"
export PYTHONPATH=/home/pedro/dev/sandbox/LivChatSetup
# E2E tests run by default. To skip: export SKIP_E2E_TESTS=true
```

### 2. Executar Teste em Background com Monitoramento Foreground

```bash
# RECOMENDADO: Teste em background + sleep em foreground para monitoramento
# Iniciar teste completo em background
pytest tests/e2e/test_complete_e2e_workflow.py::TestCompleteE2EWorkflow::test_complete_infrastructure_workflow \
    -xvs --tb=line --timeout=1800 > test.log 2>&1 &

# Capturar o PID
TEST_PID=$!
echo "🚀 Teste iniciado com PID: $TEST_PID"

# IMPORTANTE: Use sleep em FOREGROUND (não em background) para monitorar
# Isso permite acompanhar o progresso enquanto o teste roda em background
```

### 3. Monitoramento com Sleep Visual

```bash
# Sleep com progresso visual (RECOMENDADO)
echo "⏰ Aguardando 60 segundos..." && sleep 60 && echo "✅ 60 segundos completos"

# Sleep mais longo
echo "⏰ Aguardando 90 segundos para Docker/Swarm..." && sleep 90 && echo "✅ Verificando..."

# Sleep com múltiplas etapas
for i in 1 2 3; do
    echo "⏰ Etapa $i/3: Aguardando 60s..."
    sleep 60
    echo "✅ Etapa $i completa"
    tail -20 test.log | grep -E "(Criando|Docker|Portainer|PASSED|FAILED)"
done
```

### 4. Verificar Progresso em Tempo Real

```bash
# Ver últimas linhas do log
tail -f test.log | grep --color=auto -E "(✓|✅|❌|PASSED|FAILED|ERROR)"

# Filtrar por componente específico
tail -100 test.log | grep -i portainer

# Verificar se ainda está rodando
ps -p $TEST_PID && echo "🔄 Ainda executando..." || echo "✅ Finalizado"
```

## 📊 Usando Background Bash do Claude

```python
# 1. Iniciar teste em background
from subprocess import Popen
process = Popen([
    'pytest',
    'tests/e2e/test_complete_e2e_workflow.py::TestRealInfrastructure::test_real_complete_app_deployment_flow',
    '-xvs', '--tb=line'
], stdout=PIPE, stderr=PIPE, text=True)

# 2. Monitorar com sleep
import time
for i in range(5):
    time.sleep(60)
    print(f"⏰ Minuto {i+1}/5 - Teste em execução...")

# 3. Verificar resultado
if process.poll() is None:
    print("🔄 Ainda rodando...")
else:
    print(f"✅ Finalizado com código: {process.returncode}")
```

## 🚀 Debug Rápido via SSH (RECOMENDADO)

### Por que usar SSH direto?

Acessar diretamente o servidor via SSH durante os testes E2E acelera significativamente o desenvolvimento:
- **Feedback imediato**: Verificar estado sem esperar novo ciclo de teste
- **Correções rápidas**: Aplicar fixes diretamente e validar
- **Debug eficiente**: Ver logs e estado em tempo real
- **Iteração rápida**: Testar comandos antes de adicionar ao código

### Como fazer debug SSH durante testes

```bash
# 1. Obter IP do servidor existente
IP=$(hcloud server ip e2e-complete-test)
SSH_KEY="/tmp/livchat_e2e_complete/ssh_keys/e2e-complete-test_key"

# 2. Conectar ao servidor (com flags para evitar problemas de host key)
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i $SSH_KEY root@$IP

# 3. Comandos úteis para debug
# Verificar Docker e Swarm
docker info | grep Swarm
docker node ls
docker stack ls
docker service ls

# Verificar Portainer
docker service ps portainer_portainer
docker service logs portainer_portainer --tail 50
curl -k https://localhost:9443/api/system/status

# Verificar Traefik
docker service ps traefik_traefik
docker service logs traefik_traefik --tail 50

# Ver secrets do Docker
docker secret ls

# Criar diretórios necessários (ex: Portainer)
mkdir -p /var/lib/portainer

# Re-deploy de stack manualmente
docker stack deploy -c /tmp/stack.yml portainer
```

### Workflow de Debug Recomendado

1. **Iniciar teste em background**
2. **Monitorar com sleep foreground**
3. **Quando encontrar erro, conectar via SSH**
4. **Aplicar correção diretamente**
5. **Validar correção**
6. **Adicionar fix ao código**

## 🔍 Comandos de Monitoramento Úteis

```bash
# Status do servidor na Hetzner
hcloud server describe e2e-complete-test

# Verificar Traefik
ssh -i /tmp/*/ssh_keys/e2e-complete-test_key root@IP "docker service ls"

# Verificar Portainer
curl -k https://IP:9443/api/system/status

# Logs do Docker
ssh -i /tmp/*/ssh_keys/e2e-complete-test_key root@IP "docker service logs traefik_traefik"
```

## ⏱️ Tempos Esperados

| Etapa | Tempo | Visual |
|-------|-------|--------|
| Criar servidor | ~20s | `🖥️ Criando...` |
| SSH disponível | ~30s | `🔑 Aguardando SSH...` |
| Base setup | ~2min | `🔧 Setup base...` |
| Docker install | ~1.5min | `🐳 Docker...` |
| Swarm init | ~30s | `🐝 Swarm...` |
| Traefik | ~30s | `🔀 Traefik...` |
| Portainer | ~1min | `📊 Portainer...` |
| **Total** | **~6min** | `✅ Completo` |

## 🐛 Debug Rápido

```bash
# Se o teste falhar, verificar servidor
hcloud server list | grep e2e

# SSH direto no servidor
ssh -i /tmp/livchat*/ssh_keys/e2e-complete-test_key root@$(hcloud server ip e2e-complete-test)

# Ver estado dos serviços
docker stack ls
docker service ls

# Limpar servidor se necessário
hcloud server delete e2e-complete-test
```

## ⚠️ Problemas Conhecidos e Soluções

1. **DNS Cloudflare**: API error `'SyncV4PagePaginationArray[Zone]' object is not subscriptable`
   - **Solução**: Verificar token e permissões da API Cloudflare

2. **Portainer data directory missing**:
   - **Erro**: `bind source path does not exist: /var/lib/portainer`
   - **Solução**: Adicionado criação de diretório em `generic-stack-deploy.yml`

3. **Docker secret missing para Portainer**:
   - **Erro**: `secret not found: portainer_admin_password`
   - **Solução**: Adicionado criação de secret em `generic-stack-deploy.yml`

4. **Autenticação Portainer falha após re-deploy manual**:
   - **Erro**: `Invalid credentials` ao tentar deploy de apps subsequentes
   - **Causa**: Deploy manual de Portainer via SSH cria novas credenciais que conflitam
   - **Solução**:
     - Evitar re-deploy manual durante testes
     - Se necessário re-deploy, usar mesma senha do vault
     - Deletar servidor e reiniciar teste do zero (recomendado)

## 📝 Best Practices para Testes E2E

1. **SEMPRE usar venv**: `source venv/bin/activate`
2. **Executar teste em background**: Permite continuar usando o terminal
3. **Sleep em foreground**: Para monitorar progresso sem bloquear
4. **Reusar servidor existente**: Economiza tempo e recursos
5. **Debug via SSH**: Mais rápido que re-executar teste completo
6. **Verificar logs em tempo real**: `tail -f test.log`

## 🧹 Limpeza Antes de Novo Teste

**IMPORTANTE**: Se houve deploy manual ou erro de autenticação, limpe o ambiente:

```bash
# 1. Deletar servidor existente
hcloud server delete e2e-complete-test

# 2. Limpar estado local
rm -rf /tmp/livchat_e2e_complete

# 3. Verificar que servidor foi removido
hcloud server list | grep e2e
```

## 🎯 Comando Recomendado para Teste Completo

```bash
# Setup completo com monitoramento visual
pytest tests/e2e/test_complete_e2e_workflow.py::TestCompleteE2EWorkflow::test_complete_infrastructure_workflow \
    -xvs --tb=line --timeout=1800 &

# Monitorar com sleep visual
for i in {1..10}; do
    echo "⏰ [$i/10] Aguardando 30s..." && sleep 30
    echo "📊 Status:" && ps aux | grep pytest | head -1
done
```

---

**Versão**: 3.0.0
**Foco**: Workflow de Monitoramento com Sleep Visual
**Última atualização**: 2025-01-19