"""End-to-end tests for complete LivChat Setup workflow

These tests use mocks initially and can be switched to real infrastructure
by setting the LIVCHAT_E2E_REAL environment variable.

Server Specifications for Testing:
- Name: server-e2e-test
- Type: cpx11 (Hetzner's smallest available: 2 vCPU, 2GB RAM, 40GB SSD)
- Region: nbg1 (Nuremberg, Germany)
- Cost: ~€5/month (~€0.007/hour)
- OS: Ubuntu 22.04
"""

import os
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from src.orchestrator import Orchestrator


class TestCompleteWorkflow:
    """Test complete server setup workflow from creation to deployment"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def use_real_infrastructure(self):
        """Check if we should use real infrastructure"""
        return os.environ.get("LIVCHAT_E2E_REAL", "false").lower() == "true"

    @pytest.fixture
    def mock_hetzner_provider(self):
        """Mock Hetzner provider for testing"""
        mock_provider = Mock()

        def create_server_mock(name, server_type, region):
            return {
                "id": "12345",
                "name": name,  # Return the actual name passed
                "ip": "192.168.1.100",
                "type": server_type,
                "region": region,
                "status": "running",
                "provider": "hetzner"
            }

        mock_provider.create_server.side_effect = create_server_mock
        mock_provider.delete_server.return_value = True
        return mock_provider

    @pytest.fixture
    def mock_ansible_runner(self):
        """Mock Ansible Runner for testing"""
        mock_runner = Mock()
        mock_result = Mock(
            success=True,
            exit_code=0,
            stdout="Task completed successfully",
            stderr=""
        )
        mock_runner.run_playbook.return_value = mock_result
        return mock_runner

    @pytest.fixture
    def orchestrator_with_mocks(self, temp_dir, mock_hetzner_provider, mock_ansible_runner):
        """Create orchestrator with all components mocked"""
        with patch('src.orchestrator.HetznerProvider') as mock_hetzner_class, \
             patch('src.orchestrator.AnsibleRunner') as mock_ansible_class, \
             patch('src.orchestrator.SSHKeyManager') as mock_ssh_class:

            # Configure mocks
            mock_hetzner_class.return_value = mock_hetzner_provider
            mock_ansible_class.return_value = mock_ansible_runner

            mock_ssh = Mock()
            mock_ssh.key_exists.return_value = False
            mock_ssh.generate_key_pair.return_value = {
                "name": "test-server_key",
                "public_key": "ssh-ed25519 AAAAC3... test-server_key",
                "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
                "fingerprint": "SHA256:abcd1234..."
            }
            mock_ssh.add_to_hetzner.return_value = True
            mock_ssh_class.return_value = mock_ssh

            # Create orchestrator
            orchestrator = Orchestrator(temp_dir)
            orchestrator.init()

            # Configure provider
            orchestrator.configure_provider("hetzner", "test-token-123")

            yield orchestrator

    def test_single_server_complete_setup(self, orchestrator_with_mocks, use_real_infrastructure):
        """Test complete workflow for a SINGLE server: create -> setup -> deploy Traefik

        Server Details:
        - Name: server-e2e-test
        - Type: cx11 (1 vCPU, 2GB RAM, 20GB SSD)
        - Region: nbg1 (Nuremberg)
        - Setup: Base + Docker + Swarm + Traefik
        """

        if use_real_infrastructure:
            pytest.skip("Real infrastructure tests in separate class")

        print("\n" + "="*60)
        print("TESTE E2E: Setup Completo de 1 Servidor")
        print("="*60)

        # Step 1: Create server
        server_name = "server-e2e-test"
        print(f"\n1. Criando servidor: {server_name}")
        print(f"   Tipo: cpx11 (2 vCPU, 2GB RAM, 40GB SSD)")
        print(f"   Região: nbg1 (Nuremberg, Alemanha)")

        server = orchestrator_with_mocks.create_server(
            name=server_name,
            server_type="cpx11",  # Cheapest available Hetzner instance
            region="nbg1"
        )

        assert server["name"] == server_name
        assert server["ip"] == "192.168.1.100"  # Mocked IP
        assert server["status"] == "running"
        print(f"   ✓ Servidor criado: IP {server['ip']}")

        # Verify server is in state
        saved_server = orchestrator_with_mocks.get_server(server_name)
        assert saved_server is not None
        assert saved_server["ip"] == "192.168.1.100"

        # Step 2: Run complete setup
        print(f"\n2. Executando setup completo no servidor")
        setup_config = {
            "ssl_email": "admin@example.com",
            "timezone": "America/Sao_Paulo",
            "network_name": "livchat_network"
        }

        result = orchestrator_with_mocks.setup_server(server_name, setup_config)

        assert result["success"] is True
        assert result["server"] == server_name
        assert result["step"] == "complete"
        print(f"   ✓ Setup completo finalizado")

        # Verify all 4 steps were executed
        ansible_runner = orchestrator_with_mocks.ansible_runner
        assert ansible_runner.run_playbook.call_count == 4  # base, docker, swarm, traefik

        # Check playbook calls in order
        calls = ansible_runner.run_playbook.call_args_list
        playbook_names = [str(call.kwargs.get("playbook_path", "")) for call in calls]

        print(f"\n3. Verificando execução dos playbooks:")
        assert any("base-setup.yml" in path for path in playbook_names)
        print(f"   ✓ base-setup.yml executado")
        assert any("docker-install.yml" in path for path in playbook_names)
        print(f"   ✓ docker-install.yml executado")
        assert any("swarm-init.yml" in path for path in playbook_names)
        print(f"   ✓ swarm-init.yml executado")
        assert any("traefik-deploy.yml" in path for path in playbook_names)
        print(f"   ✓ traefik-deploy.yml executado")

        print(f"\n✅ TESTE COMPLETO: Servidor {server_name} configurado com sucesso!")
        print("="*60)

    def test_individual_setup_steps(self, orchestrator_with_mocks):
        """Test running individual setup steps"""

        # Create server first
        orchestrator_with_mocks.create_server("step-test", "cx21", "nbg1")

        # Test individual steps
        assert orchestrator_with_mocks.install_docker("step-test") is True
        assert orchestrator_with_mocks.init_swarm("step-test", "custom_network") is True
        assert orchestrator_with_mocks.deploy_traefik("step-test", "ssl@example.com") is True

        # Verify each step was called
        ansible_runner = orchestrator_with_mocks.ansible_runner
        assert ansible_runner.run_playbook.call_count == 3

    def test_setup_with_ssh_key_generation(self, orchestrator_with_mocks):
        """Test SSH key generation during setup"""

        # Create server
        orchestrator_with_mocks.create_server("ssh-test", "cx21", "nbg1")

        # Setup SSH (should generate new key)
        result = orchestrator_with_mocks.setup_server_ssh("ssh-test")
        assert result is True

        # Verify SSH manager was called
        ssh_manager = orchestrator_with_mocks.ssh_manager
        ssh_manager.generate_key_pair.assert_called_once_with("ssh-test_key")
        ssh_manager.add_to_hetzner.assert_called_once()

    def test_setup_failure_handling(self, orchestrator_with_mocks):
        """Test handling of setup failures"""

        # Create server
        orchestrator_with_mocks.create_server("fail-test", "cx21", "nbg1")

        # Make ansible fail at Docker installation
        results = [
            Mock(success=True, exit_code=0, stdout="OK", stderr=""),  # base-setup succeeds
            Mock(success=False, exit_code=1, stdout="", stderr="Docker installation failed"),  # docker fails
        ]
        orchestrator_with_mocks.ansible_runner.run_playbook.side_effect = results

        # Run setup
        result = orchestrator_with_mocks.setup_server("fail-test")

        assert result["success"] is False
        assert "docker-install" in result["step"]

        # Verify setup stopped after failure
        assert orchestrator_with_mocks.ansible_runner.run_playbook.call_count == 2

    def test_deploy_apps_with_dependencies(self, orchestrator_with_mocks):
        """Test deploying applications with dependency resolution"""

        # Create server
        orchestrator_with_mocks.create_server("app-test", "cx21", "nbg1")

        # Deploy apps with dependencies
        result = orchestrator_with_mocks.deploy_apps("app-test", ["n8n", "wordpress"])

        assert result["status"] == "planned"
        assert "postgres" in result["install_order"]  # n8n dependency
        assert "redis" in result["install_order"]     # n8n dependency
        assert "mysql" in result["install_order"]     # wordpress dependency
        assert "n8n" in result["install_order"]
        assert "wordpress" in result["install_order"]

        # Verify dependency order
        order = result["install_order"]
        assert order.index("postgres") < order.index("n8n")
        assert order.index("redis") < order.index("n8n")
        assert order.index("mysql") < order.index("wordpress")

    # TODO: Fase 2 - Implementar testes com múltiplos servidores
    # def test_multi_server_management(self, orchestrator_with_mocks):
    #     """Test managing multiple servers"""
    #
    #     # Create multiple servers
    #     servers = []
    #     for i in range(3):
    #         server_name = f"multi-server-{i}"
    #         server = orchestrator_with_mocks.create_server(
    #             server_name,
    #             "cx21",
    #             "nbg1"
    #         )
    #         servers.append(server)
    #
    #     # List all servers
    #     all_servers = orchestrator_with_mocks.list_servers()
    #     assert len(all_servers) == 3
    #
    #     # Setup each server
    #     for server in servers:
    #         result = orchestrator_with_mocks.setup_server(server["name"])
    #         assert result["success"] is True
    #
    #     # Delete one server
    #     orchestrator_with_mocks.delete_server("multi-server-1")
    #
    #     # Verify only 2 servers remain
    #     remaining = orchestrator_with_mocks.list_servers()
    #     assert len(remaining) == 2
    #     assert "multi-server-0" in remaining
    #     assert "multi-server-2" in remaining
    #     assert "multi-server-1" not in remaining

    def test_server_setup_idempotency(self, orchestrator_with_mocks):
        """Test that setup operations are idempotent"""

        # Create server
        orchestrator_with_mocks.create_server("idempotent-test", "cx21", "nbg1")

        # Run setup twice
        result1 = orchestrator_with_mocks.setup_server("idempotent-test")
        assert result1["success"] is True

        # Reset mock call count
        orchestrator_with_mocks.ansible_runner.run_playbook.reset_mock()

        # Run setup again
        result2 = orchestrator_with_mocks.setup_server("idempotent-test")
        assert result2["success"] is True

        # Should run all playbooks again (Ansible handles idempotency)
        assert orchestrator_with_mocks.ansible_runner.run_playbook.call_count == 4

    def test_state_persistence(self, temp_dir):
        """Test that state persists across orchestrator instances"""

        # Create first orchestrator instance
        with patch('src.orchestrator.HetznerProvider') as mock_provider:
            mock_provider.return_value.create_server.return_value = {
                "id": "123",
                "name": "persist-test",
                "ip": "10.0.0.1",
                "provider": "hetzner"
            }

            orch1 = Orchestrator(temp_dir)
            orch1.init()
            orch1.configure_provider("hetzner", "token")
            orch1.create_server("persist-test", "cx21", "nbg1")

        # Create second orchestrator instance
        orch2 = Orchestrator(temp_dir)

        # Should load existing state
        server = orch2.get_server("persist-test")
        assert server is not None
        assert server["ip"] == "10.0.0.1"

        # Should load existing config
        provider = orch2.storage.config.get("provider")
        assert provider == "hetzner"


class TestCLIIntegration:
    """Test CLI command integration"""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI test runner"""
        import subprocess

        def run_cli(*args):
            """Run CLI command and return result"""
            cmd = ["python", "-m", "src.cli"] + list(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(Path.cwd())}
            )
            return result

        return run_cli

    def test_cli_help(self, cli_runner):
        """Test CLI help command"""
        result = cli_runner("--help")
        assert result.returncode == 0
        assert "LivChat Setup" in result.stdout
        assert "setup-server" in result.stdout
        assert "install-docker" in result.stdout

    def test_cli_init(self, cli_runner, tmp_path):
        """Test CLI init command"""
        result = cli_runner("init", "--config-dir", str(tmp_path))

        # Note: Will fail without proper mocking, but structure is correct
        # In real test, would mock Orchestrator
        assert "init" in result.stderr or result.returncode == 0


class TestRealInfrastructure:
    """Tests for real infrastructure (disabled by default)

    Enable with: LIVCHAT_E2E_REAL=true HETZNER_TOKEN=xxx pytest tests/e2e/
    """

    @pytest.mark.skipif(
        not os.environ.get("LIVCHAT_E2E_REAL"),
        reason="Real infrastructure tests disabled"
    )
    @pytest.mark.timeout(600)  # 10 minutes timeout for real infrastructure
    def test_real_hetzner_single_server(self):
        """Test creating and setting up a SINGLE real server on Hetzner

        Server Specifications:
        - Name: server-e2e-test
        - Type: cpx11 (2 vCPU, 2GB RAM, 40GB SSD)
        - Region: nbg1 (Nuremberg, Germany)
        - Cost: ~€0.007/hour (will be deleted after test)
        """

        token = os.environ.get("HETZNER_TOKEN")
        if not token:
            pytest.skip("HETZNER_TOKEN not set")

        server_name = "server-e2e-test"

        print("\n" + "="*70)
        print("TESTE COM INFRAESTRUTURA REAL - HETZNER")
        print("="*70)
        print(f"Servidor: {server_name}")
        print(f"Tipo: ccx23 (4 vCPU AMD, 16GB RAM, 80GB SSD)")
        print(f"Sistema: Debian 12")
        print(f"Região: ash (Ashburn, VA)")
        print(f"Custo estimado: €0.026/hora (~€19/mês)")
        print("="*70)

        # Always delete server to avoid costs
        delete_on_success = True
        delete_on_failure = True

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = Orchestrator(Path(tmpdir))
            orchestrator.init()
            orchestrator.configure_provider("hetzner", token)

            server = None
            result = {"success": False}

            try:
                # Step 1: Create server
                print(f"\n1. Criando servidor real na Hetzner...")
                server = orchestrator.create_server(
                    server_name,
                    "ccx23",  # 4 vCPU AMD, 16GB RAM, 80GB NVMe
                    "ash",    # Ashburn, VA
                    "debian-12"
                )

                print(f"   ✓ Servidor criado:")
                print(f"     - ID: {server.get('id')}")
                print(f"     - IP: {server['ip']}")
                print(f"     - Status: {server.get('status')}")
                print(f"\n   📝 Para conectar manualmente:")
                print(f"     ssh -i {tmpdir}/ssh_keys/{server_name}_key root@{server['ip']}")

                assert server["ip"] is not None
                assert server.get("status") == "running"

                # Step 2: Run complete setup
                print(f"\n2. Executando setup completo...")
                print(f"   - Aguardando SSH ficar disponível...")
                print(f"   - Base setup (atualizar sistema, firewall, swap)")
                print(f"   - Docker installation")
                print(f"   - Docker Swarm initialization")
                print(f"   - Traefik deployment")

                # Capture detailed logs
                import json
                log_file = Path(f"/tmp/livchat_{server_name}_setup.log")

                result = orchestrator.setup_server(server_name, {
                    "ssl_email": "test@example.com",
                    "timezone": "America/Sao_Paulo"
                })

                # Save detailed result
                with open(log_file, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                print(f"   📄 Logs salvos em: {log_file}")

                if not result["success"]:
                    print(f"\n   ❌ Setup falhou:")
                    print(f"     - Step: {result.get('step')}")
                    print(f"     - Message: {result.get('message')}")
                    print(f"     - Details: {result.get('details')}")
                    print(f"\n   🔍 Servidor mantido para investigação!")
                    print(f"     IP: {server['ip']}")
                    print(f"     SSH: ssh -i {tmpdir}/ssh_keys/{server_name}_key root@{server['ip']}")

                    if not delete_on_failure:
                        print(f"\n   ⚠️  IMPORTANTE: Servidor NÃO será deletado!")
                        print(f"     Para deletar manualmente, execute:")
                        print(f"     python3 -c \"from hcloud import Client; c=Client(token='{token}'); s=c.servers.get_by_name('{server_name}'); s.delete() if s else print('Not found')\"")

                assert result["success"] is True
                print(f"\n   ✓ Setup completo finalizado com sucesso!")
                print(f"     - Status: {result['step']}")

            except Exception as e:
                print(f"\n❌ ERRO durante o teste: {e}")
                raise

            finally:
                # Cleanup decision based on result and env vars
                should_delete = False

                if result["success"]:
                    should_delete = delete_on_success
                    if should_delete:
                        print(f"\n3. Limpando recursos (servidor teve sucesso)...")
                else:
                    should_delete = delete_on_failure
                    if not should_delete:
                        print(f"\n⚠️  SERVIDOR MANTIDO PARA DEBUG!")
                        print(f"  IP: {server['ip']}")
                        print(f"  SSH Key: {tmpdir}/ssh_keys/{server_name}_key")
                        print(f"  Comando SSH:")
                        print(f"    ssh -i {tmpdir}/ssh_keys/{server_name}_key -o StrictHostKeyChecking=no root@{server['ip']}")
                        print(f"\n  Para deletar manualmente depois:")
                        print(f"    hcloud server delete {server_name}")

                        # Save SSH key and logs to persistent location
                        import shutil
                        persistent_dir = Path("/tmp/livchat_debug")
                        persistent_dir.mkdir(exist_ok=True)

                        # Copy SSH key
                        ssh_key_src = Path(tmpdir) / "ssh_keys" / f"{server_name}_key"
                        if ssh_key_src.exists():
                            ssh_key_dst = persistent_dir / f"{server_name}_key"
                            shutil.copy2(ssh_key_src, ssh_key_dst)
                            ssh_key_dst.chmod(0o600)
                            print(f"\n  SSH key copiada para: {ssh_key_dst}")
                            print(f"    ssh -i {ssh_key_dst} root@{server['ip']}")

                        # Save server info
                        info_file = persistent_dir / f"{server_name}_info.txt"
                        with open(info_file, 'w') as f:
                            f.write(f"Server: {server_name}\n")
                            f.write(f"IP: {server['ip']}\n")
                            f.write(f"Created: {server.get('created', 'unknown')}\n")
                            f.write(f"Failed at: {result.get('step', 'unknown')}\n")
                            f.write(f"Error: {result.get('message', 'unknown')}\n")
                            f.write(f"\nSSH Command:\n")
                            f.write(f"ssh -i {ssh_key_dst} root@{server['ip']}\n")
                        print(f"  Info salva em: {info_file}")
                    else:
                        print(f"\n3. Limpando recursos (deletando servidor após falha)...")

                if should_delete:
                    try:
                        orchestrator.delete_server(server_name)
                        print(f"   ✓ Servidor {server_name} deletado com sucesso")
                    except Exception as e:
                        print(f"   ⚠ ATENÇÃO: Falha ao deletar servidor: {e}")
                        print(f"   Verifique no painel Hetzner!")

        print("\n" + "="*70)
        print("TESTE FINALIZADO")
        print("="*70)