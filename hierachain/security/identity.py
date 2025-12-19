"""
Identity Management Module

This module provides identity management services for the HieraChain system.
It handles organization registration, user management, role-based access control, and
identity validation for enterprise applications.
"""

import time
from typing import Optional, Any
import logging
from hierachain.security.security_utils import verify_signature
from nacl.encoding import HexEncoder

logger = logging.getLogger(__name__)


class IdentityError(Exception):
    """Exception raised for identity-related errors"""
    pass


class IdentityManager:
    """Simple identity management for enterprise applications"""
    
    def __init__(self):
        self.organizations: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.roles: dict[str, list[str]] = {}
    
    def register_organization(self, org_id: str, name: str, participants: Optional[list[str]] = None) -> str:
        """Register new organization"""
        self.organizations[org_id] = {
            "name": name,
            "participants": participants or [],
            "created_at": time.time()
        }
        return org_id
    
    def register_user(self, user_id: str, org_id: str, role: str, public_key: Optional[str] = None) -> str:
        """Register new user with Ed25519 public key validation."""
        if org_id not in self.organizations:
            raise IdentityError(f"Organization {org_id} does not exist")
            
        # Validate Public Key
        if public_key:
            if len(public_key) != 64:
                raise IdentityError("Public key must be a 64-character hex string (Ed25519)")
            try:
                # Try decoding to ensure it's valid hex
                HexEncoder.decode(public_key.encode('utf-8'))
            except Exception:
                raise IdentityError("Invalid public key hex format")

        self.users[user_id] = {
            "org_id": org_id,
            "role": role,
            "public_key": public_key,
            "created_at": time.time()
        }
        
        # Add to organization participants list
        self.organizations[org_id]["participants"].append(user_id)
        
        # Update roles
        if role not in self.roles:
            self.roles[role] = []
        self.roles[role].append(user_id)
        
        logger.info(f"Registered user {user_id} with role {role}")
        return user_id
    
    def validate_identity(self, user_id: str, required_role: Optional[str] = None) -> bool:
        """Validate identity and role"""
        if user_id not in self.users:
            return False
            
        if required_role and self.users[user_id]["role"] != required_role:
            return False
            
        return True

    def verify_user_signature(self, user_id: str, message: bytes, signature: str) -> bool:
        """
        Verify that a message was signed by the specific user.
        
        Args:
            user_id: The ID of the user claiming to sign.
            message: The message bytes.
            signature: The hex signature.
            
        Returns:
            bool: True if signature is valid, False otherwise.
        """
        user = self.users.get(user_id)
        if not user or not user.get("public_key"):
            logger.warning(f"Cannot verify signature: User {user_id} not found or has no public key")
            return False
            
        return verify_signature(user["public_key"], message, signature)
    
    def get_user_info(self, user_id: str) -> Optional[dict[str, Any]]:
        """Get user information"""
        return self.users.get(user_id)
    
    def get_organization_info(self, org_id: str) -> Optional[dict[str, Any]]:
        """Get organization information"""
        return self.organizations.get(org_id)
    
    def get_users_by_role(self, role: str) -> list[str]:
        """Get all users with specific role"""
        return self.roles.get(role, [])
    
    def get_users_by_organization(self, org_id: str) -> list[str]:
        """Get all users in organization"""
        if org_id not in self.organizations:
            return []
        return self.organizations[org_id]["participants"]
    
    def update_user_role(self, user_id: str, new_role: str) -> bool:
        """Update user role"""
        if user_id not in self.users:
            return False
        
        old_role = self.users[user_id]["role"]
        
        # Remove from old role
        if old_role in self.roles and user_id in self.roles[old_role]:
            self.roles[old_role].remove(user_id)
        
        # Add to new role
        if new_role not in self.roles:
            self.roles[new_role] = []
        self.roles[new_role].append(user_id)
        
        # Update user record
        self.users[user_id]["role"] = new_role
        
        return True
    
    def remove_user(self, user_id: str) -> bool:
        """Remove user from system"""
        if user_id not in self.users:
            return False
        
        user_info = self.users[user_id]
        org_id = user_info["org_id"]
        role = user_info["role"]
        
        # Remove from organization
        if org_id in self.organizations:
            if user_id in self.organizations[org_id]["participants"]:
                self.organizations[org_id]["participants"].remove(user_id)
        
        # Remove from role
        if role in self.roles and user_id in self.roles[role]:
            self.roles[role].remove(user_id)
        
        # Remove user record
        del self.users[user_id]
        
        return True
    
    def remove_organization(self, org_id: str) -> bool:
        """Remove organization and all its users"""
        if org_id not in self.organizations:
            return False
        
        # Remove all users in organization
        participants = self.organizations[org_id]["participants"].copy()
        for user_id in participants:
            self.remove_user(user_id)
        
        # Remove organization
        del self.organizations[org_id]
        
        return True
    
    def list_all_organizations(self) -> list[str]:
        """list all organization IDs"""
        return list(self.organizations.keys())
    
    def list_all_users(self) -> list[str]:
        """list all user IDs"""
        return list(self.users.keys())
    
    def list_all_roles(self) -> list[str]:
        """list all roles"""
        return list(self.roles.keys())