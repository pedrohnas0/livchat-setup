"""
Pydantic models for Application API

Request and response models for application deployment endpoints
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class AppDeployRequest(BaseModel):
    """Request to deploy an application"""
    server_name: str = Field(..., description="Name of server to deploy to")
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    domain: Optional[str] = Field(None, description="Custom domain for the app")

    class Config:
        json_schema_extra = {
            "example": {
                "server_name": "production-1",
                "environment": {
                    "N8N_HOST": "n8n.example.com",
                    "N8N_PROTOCOL": "https"
                },
                "domain": "n8n.example.com"
            }
        }


class AppDeployResponse(BaseModel):
    """Response from app deployment (returns job)"""
    job_id: str = Field(..., description="Job ID for tracking deployment progress")
    message: str = Field(..., description="Status message")
    app_name: str = Field(..., description="Name of app being deployed")
    server_name: str = Field(..., description="Target server name")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "deploy_app-abc123",
                "message": "Application deployment started",
                "app_name": "n8n",
                "server_name": "production-1"
            }
        }


class AppUndeployResponse(BaseModel):
    """Response from app undeployment (returns job)"""
    job_id: str = Field(..., description="Job ID for tracking undeployment progress")
    message: str = Field(..., description="Status message")
    app_name: str = Field(..., description="Name of app being removed")
    server_name: str = Field(..., description="Server name")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "undeploy_app-abc123",
                "message": "Application removal started",
                "app_name": "n8n",
                "server_name": "production-1"
            }
        }


class AppInfo(BaseModel):
    """Application information"""
    name: str = Field(..., description="Application name")
    version: Optional[str] = Field(None, description="Application version")
    description: Optional[str] = Field(None, description="Application description")
    category: Optional[str] = Field(None, description="Category (databases, applications, etc)")
    dependencies: List[str] = Field(default_factory=list, description="List of dependencies")
    deploy_method: str = Field(..., description="Deployment method (ansible/portainer)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "n8n",
                "version": "latest",
                "description": "Workflow automation tool",
                "category": "applications",
                "dependencies": ["postgres", "redis"],
                "deploy_method": "portainer"
            }
        }


class AppListResponse(BaseModel):
    """List of available applications"""
    apps: List[AppInfo] = Field(..., description="List of available apps")
    total: int = Field(..., description="Total number of apps")

    class Config:
        json_schema_extra = {
            "example": {
                "apps": [
                    {
                        "name": "n8n",
                        "version": "latest",
                        "description": "Workflow automation",
                        "category": "applications",
                        "dependencies": ["postgres", "redis"],
                        "deploy_method": "portainer"
                    },
                    {
                        "name": "postgres",
                        "version": "14",
                        "description": "PostgreSQL database",
                        "category": "databases",
                        "dependencies": [],
                        "deploy_method": "portainer"
                    }
                ],
                "total": 2
            }
        }


class DeployedAppInfo(BaseModel):
    """Information about a deployed application"""
    app_name: str = Field(..., description="Application name")
    server_name: str = Field(..., description="Server where app is deployed")
    domain: Optional[str] = Field(None, description="Domain configured for app")
    status: str = Field(..., description="Deployment status")
    deployed_at: Optional[str] = Field(None, description="Deployment timestamp")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

    class Config:
        json_schema_extra = {
            "example": {
                "app_name": "n8n",
                "server_name": "production-1",
                "domain": "n8n.example.com",
                "status": "running",
                "deployed_at": "2024-12-16T10:00:00",
                "environment": {
                    "N8N_HOST": "n8n.example.com"
                }
            }
        }


class DeployedAppListResponse(BaseModel):
    """List of deployed applications on a server"""
    apps: List[DeployedAppInfo] = Field(..., description="List of deployed apps")
    server_name: str = Field(..., description="Server name")
    total: int = Field(..., description="Total number of deployed apps")

    class Config:
        json_schema_extra = {
            "example": {
                "apps": [
                    {
                        "app_name": "n8n",
                        "server_name": "production-1",
                        "domain": "n8n.example.com",
                        "status": "running",
                        "deployed_at": "2024-12-16T10:00:00",
                        "environment": {}
                    }
                ],
                "server_name": "production-1",
                "total": 1
            }
        }
