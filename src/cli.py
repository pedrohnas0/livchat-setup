"""Command-line interface for LivChat Setup"""

import sys
import argparse
import asyncio
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
    config_parser = subparsers.add_parser('configure', help='Configure provider or settings')
    config_parser.add_argument('provider', nargs='?', help='Provider name (e.g., hetzner)')
    config_parser.add_argument('--token', help='API token for provider')
    config_parser.add_argument('--admin-email', help='Default admin email for applications')

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

    # Deploy Portainer command
    portainer_parser = subparsers.add_parser('deploy-portainer', help='Deploy Portainer CE')
    portainer_parser.add_argument('name', help='Server name')
    portainer_parser.add_argument('--admin-password', help='Admin password (default: admin123!@#)')
    portainer_parser.add_argument('--https-port', type=int, default=9443, help='HTTPS port (default: 9443)')

    # Configure Cloudflare command
    cloudflare_parser = subparsers.add_parser('configure-cloudflare', help='Configure Cloudflare API')
    cloudflare_parser.add_argument('email', help='Cloudflare account email')
    cloudflare_parser.add_argument('api_key', help='Cloudflare Global API Key')

    # Setup DNS command
    dns_parser = subparsers.add_parser('setup-dns', help='Setup DNS for a server')
    dns_parser.add_argument('server', help='Server name')
    dns_parser.add_argument('zone', help='Cloudflare zone name (e.g., livchat.ai)')
    dns_parser.add_argument('--subdomain', help='Optional subdomain (e.g., lab, dev)')

    # Add app DNS command
    app_dns_parser = subparsers.add_parser('add-app-dns', help='Add DNS for an application')
    app_dns_parser.add_argument('app', help='Application name (e.g., chatwoot, n8n)')
    app_dns_parser.add_argument('zone', help='Cloudflare zone name')
    app_dns_parser.add_argument('--subdomain', help='Optional subdomain')

    # List available apps command
    list_apps_parser = subparsers.add_parser('list-apps', help='List available applications')
    list_apps_parser.add_argument('--category', help='Filter by category (e.g., database, automation)')

    # Deploy app command
    deploy_app_parser = subparsers.add_parser('deploy-app', help='Deploy an application to a server')
    deploy_app_parser.add_argument('server', help='Server name')
    deploy_app_parser.add_argument('app', help='Application name (e.g., postgres, n8n, chatwoot)')
    deploy_app_parser.add_argument('--config', help='JSON configuration for the app')

    # Delete app command
    delete_app_parser = subparsers.add_parser('delete-app', help='Delete an application from a server')
    delete_app_parser.add_argument('server', help='Server name')
    delete_app_parser.add_argument('app', help='Application name')

    # App status command
    app_status_parser = subparsers.add_parser('app-status', help='Check application status')
    app_status_parser.add_argument('server', help='Server name')
    app_status_parser.add_argument('--app', help='Specific app name (optional)')

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
            # Configure admin email if provided
            if hasattr(args, 'admin_email') and args.admin_email:
                setup.storage.config.set('admin_email', args.admin_email)
                setup.storage.config.save()
                print(f"✅ Admin email configured: {args.admin_email}")

            # Configure provider if provided
            if args.provider and args.token:
                setup.configure_provider(args.provider, args.token)
                print(f"✅ Provider {args.provider} configured successfully")
            elif args.provider and not args.token:
                print("❌ Error: --token is required when configuring a provider")
                return 1
            elif not args.provider and not args.admin_email:
                print("❌ Error: Specify a provider with --token, or use --admin-email to set admin email")
                return 1

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

        elif args.command == 'deploy-portainer':
            config = {}
            if hasattr(args, 'admin_password') and args.admin_password:
                config['portainer_admin_password'] = args.admin_password
            if hasattr(args, 'https_port') and args.https_port:
                config['portainer_https_port'] = args.https_port

            print(f"📊 Deploying Portainer on {args.name}...")
            result = setup.deploy_portainer(args.name, config)

            if result:
                print(f"✅ Portainer deployed successfully on {args.name}!")
                server = setup.storage.state.get_server(args.name)
                if server:
                    print(f"   Access URL: https://{server.get('ip', 'N/A')}:{config.get('portainer_https_port', 9443)}")
                    print(f"   Username: admin")
                    print(f"   Password: {config.get('portainer_admin_password', 'admin123!@#')}")
            else:
                print(f"❌ Failed to deploy Portainer")
                return 1

        elif args.command == 'configure-cloudflare':
            print(f"☁️ Configuring Cloudflare API...")
            if setup.configure_cloudflare(args.email, args.api_key):
                print(f"✅ Cloudflare configured successfully")
                print(f"   Email: {args.email}")
            else:
                print(f"❌ Failed to configure Cloudflare")
                return 1

        elif args.command == 'setup-dns':
            server = setup.get_server(args.server)
            if not server:
                print(f"❌ Server {args.server} not found")
                return 1

            print(f"🌐 Setting up DNS for server {args.server}...")

            # Run async function
            result = asyncio.run(setup.setup_dns_for_server(
                args.server, args.zone, args.subdomain
            ))

            if result['success']:
                print(f"✅ DNS configured successfully")
                print(f"   Record: {result.get('record_name', 'N/A')}")
                print(f"   IP: {server['ip']}")
            else:
                print(f"❌ Failed to setup DNS: {result.get('error', 'Unknown error')}")
                return 1

        elif args.command == 'add-app-dns':
            print(f"🌐 Adding DNS for application {args.app}...")

            # Run async function
            result = asyncio.run(setup.add_app_dns(
                args.app, args.zone, args.subdomain
            ))

            if result['success']:
                print(f"✅ DNS configured for {args.app}")
                print(f"   Records created: {result.get('records_created', 0)}")

                # Show details if available
                if 'details' in result:
                    for detail in result['details']:
                        if detail.get('success'):
                            print(f"   • {detail.get('record_name', 'N/A')}")
            else:
                print(f"❌ Failed to add app DNS: {result.get('error', 'Unknown error')}")
                return 1

        elif args.command == 'list-apps':
            # List available applications
            category = getattr(args, 'category', None)
            apps = setup.list_available_apps(category=category)

            if apps:
                print(f"📦 Available Applications{f' ({category})' if category else ''}:")
                for app in apps:
                    print(f"  • {app['name']} ({app['category']}) - {app['description']}")
                    if app.get('has_dependencies'):
                        print(f"    Has dependencies: Yes")
            else:
                print(f"No applications found{f' in category {category}' if category else ''}")

        elif args.command == 'deploy-app':
            print(f"🚀 Deploying {args.app} to server {args.server}...")

            # Parse config if provided
            config = {}
            if hasattr(args, 'config') and args.config:
                try:
                    import json
                    config = json.loads(args.config)
                except Exception as e:
                    print(f"❌ Invalid config JSON: {e}")
                    return 1

            # Deploy the application
            result = asyncio.run(setup.deploy_app(args.server, args.app, config))

            if result.get('success'):
                print(f"✅ {args.app} deployed successfully on {args.server}")
                if result.get('dns_configured'):
                    print(f"   DNS configured: Yes")
                if result.get('stack_id'):
                    print(f"   Stack ID: {result['stack_id']}")
                if result.get('dependencies_resolved'):
                    print(f"   Dependencies: {', '.join(result['dependencies_resolved'])}")
            else:
                print(f"❌ Failed to deploy {args.app}: {result.get('error', 'Unknown error')}")
                return 1

        elif args.command == 'delete-app':
            print(f"🗑️ Deleting {args.app} from server {args.server}...")

            # Confirm deletion
            response = input(f"Are you sure you want to delete {args.app}? (y/N): ")
            if response.lower() != 'y':
                print("Deletion cancelled")
                return 0

            # Delete the application
            result = asyncio.run(setup.delete_app(args.server, args.app))

            if result.get('success'):
                print(f"✅ {args.app} deleted successfully from {args.server}")
            else:
                print(f"❌ Failed to delete {args.app}: {result.get('error', 'Unknown error')}")
                return 1

        elif args.command == 'app-status':
            server = setup.get_server(args.server)
            if not server:
                print(f"❌ Server {args.server} not found")
                return 1

            apps = server.get('applications', [])
            if not apps:
                print(f"No applications installed on {args.server}")
            else:
                print(f"📊 Applications on {args.server}:")
                for app in apps:
                    if not args.app or app == args.app:
                        print(f"  • {app}: Running")  # TODO: Get actual status from Portainer

        return 0

    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())