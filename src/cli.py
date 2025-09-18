"""Command-line interface for LivChat Setup"""

import sys
import argparse
import logging
from pathlib import Path

try:
    from .orchestrator import Orchestrator
except ImportError:
    # For direct execution
    from orchestrator import Orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="LivChat Setup - Automated server setup and deployment"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize LivChat Setup')
    init_parser.add_argument('--config-dir', type=Path, help='Configuration directory')

    # Configure command
    config_parser = subparsers.add_parser('configure', help='Configure provider')
    config_parser.add_argument('provider', help='Provider name (e.g., hetzner)')
    config_parser.add_argument('--token', required=True, help='API token')

    # Create server command
    create_parser = subparsers.add_parser('create-server', help='Create a new server')
    create_parser.add_argument('name', help='Server name')
    create_parser.add_argument('--type', default='cx21', help='Server type')
    create_parser.add_argument('--region', default='nbg1', help='Region/location')

    # List servers command
    list_parser = subparsers.add_parser('list-servers', help='List all servers')

    # Delete server command
    delete_parser = subparsers.add_parser('delete-server', help='Delete a server')
    delete_parser.add_argument('name', help='Server name')

    # Setup server command
    setup_parser = subparsers.add_parser('setup-server', help='Run complete server setup')
    setup_parser.add_argument('name', help='Server name')
    setup_parser.add_argument('--ssl-email', help='Email for SSL certificates')
    setup_parser.add_argument('--timezone', default='America/Sao_Paulo', help='Server timezone')

    # Install Docker command
    docker_parser = subparsers.add_parser('install-docker', help='Install Docker on server')
    docker_parser.add_argument('name', help='Server name')

    # Init Swarm command
    swarm_parser = subparsers.add_parser('init-swarm', help='Initialize Docker Swarm')
    swarm_parser.add_argument('name', help='Server name')
    swarm_parser.add_argument('--network', default='livchat_network', help='Overlay network name')

    # Deploy Traefik command
    traefik_parser = subparsers.add_parser('deploy-traefik', help='Deploy Traefik reverse proxy')
    traefik_parser.add_argument('name', help='Server name')
    traefik_parser.add_argument('--ssl-email', help='Email for Let\'s Encrypt')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize Orchestrator
    config_dir = getattr(args, 'config_dir', None)
    setup = Orchestrator(config_dir)

    # Execute command
    try:
        if args.command == 'init':
            setup.init()
            print("✅ LivChat Setup initialized successfully")
            print(f"Configuration directory: {setup.config_dir}")

        elif args.command == 'configure':
            setup.configure_provider(args.provider, args.token)
            print(f"✅ Provider {args.provider} configured successfully")

        elif args.command == 'create-server':
            server = setup.create_server(args.name, args.type, args.region)
            print(f"✅ Server created successfully")
            print(f"Name: {server['name']}")
            print(f"IP: {server['ip']}")
            print(f"Type: {server['type']}")
            print(f"Region: {server['region']}")

        elif args.command == 'list-servers':
            servers = setup.list_servers()
            if servers:
                print("📋 Managed servers:")
                for name, server in servers.items():
                    print(f"  • {name}: {server.get('ip', 'N/A')} ({server.get('status', 'unknown')})")
            else:
                print("No servers found")

        elif args.command == 'delete-server':
            if setup.delete_server(args.name):
                print(f"✅ Server {args.name} deleted successfully")
            else:
                print(f"❌ Failed to delete server {args.name}")
                return 1

        elif args.command == 'setup-server':
            config = {}
            if hasattr(args, 'ssl_email') and args.ssl_email:
                config['ssl_email'] = args.ssl_email
            if hasattr(args, 'timezone') and args.timezone:
                config['timezone'] = args.timezone

            print(f"🚀 Starting complete setup for server {args.name}...")
            result = setup.setup_server(args.name, config)

            if result['success']:
                print(f"✅ Server {args.name} setup completed successfully!")
                print(f"   Step: {result['step']}")
                if 'details' in result:
                    print(f"   Details: {result['details']}")
            else:
                print(f"❌ Server setup failed: {result['message']}")
                return 1

        elif args.command == 'install-docker':
            print(f"🐳 Installing Docker on {args.name}...")
            if setup.install_docker(args.name):
                print(f"✅ Docker installed successfully on {args.name}")
            else:
                print(f"❌ Failed to install Docker on {args.name}")
                return 1

        elif args.command == 'init-swarm':
            network = getattr(args, 'network', 'livchat_network')
            print(f"🐝 Initializing Docker Swarm on {args.name}...")
            if setup.init_swarm(args.name, network):
                print(f"✅ Docker Swarm initialized successfully")
                print(f"   Network: {network}")
            else:
                print(f"❌ Failed to initialize Docker Swarm")
                return 1

        elif args.command == 'deploy-traefik':
            ssl_email = getattr(args, 'ssl_email', None)
            print(f"🔄 Deploying Traefik on {args.name}...")
            if setup.deploy_traefik(args.name, ssl_email):
                print(f"✅ Traefik deployed successfully")
                if ssl_email:
                    print(f"   SSL Email: {ssl_email}")
            else:
                print(f"❌ Failed to deploy Traefik")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())