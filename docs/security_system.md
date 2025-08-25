# vprism Financial Data Platform - 安全认证系统

## 安全架构概述

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   身份认证层    │────│   授权控制层    │────│   数据访问层    │
│   JWT Token     │    │   RBAC权限    │    │   审计日志    │
│   API Key       │    │   角色管理    │    │   敏感数据    │
│   OAuth2        │    │   权限校验    │    │   加密存储    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 1. 身份认证模块 (vprism/auth/authentication.py)

```python
"""
身份认证系统 - 提供多种认证方式
"""

import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from vprism.core.database import get_db
from vprism.core.models import User, ApiKey, AuditLog


class AuthenticationManager:
    """身份认证管理器"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.security = HTTPBearer()
        self.secret_key = "your-secret-key-change-in-production"
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """生成密码哈希"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, user_id: int) -> str:
        """创建刷新令牌"""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode = {"sub": str(user_id), "exp": expire, "type": "refresh"}
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """验证令牌"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                raise HTTPException(status_code=401, detail="Invalid token type")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def generate_api_key(self) -> tuple[str, str]:
        """生成API密钥"""
        prefix = "vpr_"
        key = secrets.token_urlsafe(32)
        api_key = prefix + key
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key, hashed_key
    
    def verify_api_key(self, api_key: str, db: Session) -> Optional[User]:
        """验证API密钥"""
        if not api_key.startswith("vpr_"):
            return None
        
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        db_key = db.query(ApiKey).filter(ApiKey.hashed_key == hashed_key).first()
        
        if not db_key or not db_key.is_active:
            return None
        
        # 更新最后使用时间
        db_key.last_used = datetime.utcnow()
        db.commit()
        
        return db_key.user


# 全局认证管理器实例
auth_manager = AuthenticationManager()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(auth_manager.security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前认证用户"""
    payload = auth_manager.verify_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_api_key_user(
    api_key: str = Security(HTTPBearer()),
    db: Session = Depends(get_db)
) -> User:
    """通过API密钥获取用户"""
    user = auth_manager.verify_api_key(api_key.credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user
```

## 2. 权限管理模块 (vprism/auth/authorization.py)

```python
"""
权限管理系统 - 基于RBAC的角色权限控制
"""

from typing import List, Optional
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from vprism.core.database import get_db
from vprism.core.models import User, Role, Permission


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions
    
    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        """检查用户权限"""
        if not current_user.roles:
            raise HTTPException(status_code=403, detail="No roles assigned")
        
        user_permissions = set()
        for role in current_user.roles:
            user_permissions.update([p.name for p in role.permissions])
        
        missing_permissions = set(self.required_permissions) - user_permissions
        if missing_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permissions: {', '.join(missing_permissions)}"
            )
        
        return current_user


class RoleManager:
    """角色管理器"""
    
    @staticmethod
    def create_role(name: str, description: str, permissions: List[str], db: Session) -> Role:
        """创建角色"""
        role = Role(name=name, description=description)
        
        for perm_name in permissions:
            permission = db.query(Permission).filter(Permission.name == perm_name).first()
            if permission:
                role.permissions.append(permission)
        
        db.add(role)
        db.commit()
        return role
    
    @staticmethod
    def assign_role_to_user(user_id: int, role_name: str, db: Session) -> bool:
        """为用户分配角色"""
        user = db.query(User).filter(User.id == user_id).first()
        role = db.query(Role).filter(Role.name == role_name).first()
        
        if not user or not role:
            return False
        
        user.roles.append(role)
        db.commit()
        return True


# 预定义角色和权限
DEFAULT_ROLES = {
    "admin": {
        "description": "系统管理员",
        "permissions": [
            "read:market_data",
            "write:market_data",
            "admin:users",
            "admin:system",
            "read:audit_logs"
        ]
    },
    "analyst": {
        "description": "数据分析师",
        "permissions": [
            "read:market_data",
            "read:company_data",
            "export:data",
            "create:reports"
        ]
    },
    "developer": {
        "description": "开发者",
        "permissions": [
            "read:market_data",
            "read:api_docs",
            "test:api"
        ]
    },
    "viewer": {
        "description": "只读用户",
        "permissions": [
            "read:market_data"
        ]
    }
}


# 权限装饰器
RequireAdmin = PermissionChecker(["admin:users"])
RequireAnalyst = PermissionChecker(["read:market_data"])
RequireDeveloper = PermissionChecker(["read:api_docs"])
```

## 3. 审计日志模块 (vprism/auth/audit.py)

```python
"""
审计日志系统 - 记录用户操作和系统事件
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from vprism.core.models import AuditLog, User
from vprism.core.database import get_db


class AuditLogger:
    """审计日志记录器"""
    
    @staticmethod
    def log_user_action(
        user_id: int,
        action: str,
        resource: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        db: Session = None
    ) -> AuditLog:
        """记录用户操作"""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=json.dumps(details),
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )
        
        if db:
            db.add(audit_log)
            db.commit()
        
        return audit_log
    
    @staticmethod
    def log_system_event(
        event_type: str,
        details: Dict[str, Any],
        severity: str = "info",
        db: Session = None
    ) -> AuditLog:
        """记录系统事件"""
        audit_log = AuditLog(
            action=event_type,
            resource="system",
            details=json.dumps(details),
            severity=severity,
            timestamp=datetime.utcnow()
        )
        
        if db:
            db.add(audit_log)
            db.commit()
        
        return audit_log
    
    @staticmethod
    def get_user_activity(
        user_id: int,
        limit: int = 100,
        db: Session = None
    ) -> list:
        """获取用户活动记录"""
        if not db:
            return []
        
        return db.query(AuditLog)\
                .filter(AuditLog.user_id == user_id)\
                .order_by(AuditLog.timestamp.desc())\
                .limit(limit)\
                .all()
    
    @staticmethod
    def get_security_events(
        start_date: datetime,
        end_date: datetime,
        db: Session = None
    ) -> list:
        """获取安全事件"""
        if not db:
            return []
        
        return db.query(AuditLog)\
                .filter(AuditLog.timestamp.between(start_date, end_date))\
                .filter(AuditLog.severity.in_(["warning", "error", "critical"]))\
                .order_by(AuditLog.timestamp.desc())\
                .all()
```

## 4. 数据加密模块 (vprism/auth/encryption.py)

```python
"""
数据加密系统 - 敏感数据加密存储
"""

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional
import os


class DataEncryption:
    """数据加密工具"""
    
    def __init__(self, password: Optional[str] = None):
        if password:
            self.key = self._derive_key(password)
        else:
            self.key = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key())
        
        self.cipher = Fernet(self.key)
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """加密数据"""
        encrypted = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(encrypted)
        return decrypted.decode()
    
    def encrypt_sensitive_data(self, data: dict) -> dict:
        """加密敏感数据字典"""
        encrypted = {}
        for key, value in data.items():
            if key in ["password", "api_key", "secret", "token"]:
                encrypted[key] = self.encrypt(str(value))
            else:
                encrypted[key] = value
        return encrypted
    
    def decrypt_sensitive_data(self, encrypted_data: dict) -> dict:
        """解密敏感数据字典"""
        decrypted = {}
        for key, value in encrypted_data.items():
            if key in ["password", "api_key", "secret", "token"]:
                decrypted[key] = self.decrypt(str(value))
            else:
                decrypted[key] = value
        return decrypted


# 全局加密实例
encryption_manager = DataEncryption()
```

## 5. 安全配置集成 (vprism/auth/middleware.py)

```python
"""
安全中间件 - 集成所有安全功能
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Dict, Any
from sqlalchemy.orm import Session

from vprism.auth.audit import AuditLogger
from vprism.core.database import get_db


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.rate_limiter = {}
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 请求前处理
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # 速率限制检查
        if self._is_rate_limited(client_ip):
            return Response(
                content="Rate limit exceeded",
                status_code=429
            )
        
        # 继续处理请求
        response = await call_next(request)
        
        # 请求后处理 - 记录审计日志
        process_time = time.time() - start_time
        
        # 记录重要操作
        if request.method in ["POST", "PUT", "DELETE"]:
            db = next(get_db())
            AuditLogger.log_user_action(
                user_id=getattr(request.state, "user_id", None),
                action=f"{request.method}_{request.url.path}",
                resource=request.url.path,
                details={
                    "method": request.method,
                    "status_code": response.status_code,
                    "processing_time": process_time,
                    "ip": client_ip
                },
                ip_address=client_ip,
                user_agent=user_agent,
                db=db
            )
        
        # 添加安全头部
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
    
    def _is_rate_limited(self, ip: str) -> bool:
        """检查IP是否超过速率限制"""
        current_time = time.time()
        
        if ip not in self.rate_limiter:
            self.rate_limiter[ip] = []
        
        # 清理旧的记录
        self.rate_limiter[ip] = [
            timestamp for timestamp in self.rate_limiter[ip]
            if current_time - timestamp < 60
        ]
        
        # 检查是否超过限制 (100 requests per minute)
        if len(self.rate_limiter[ip]) >= 100:
            return True
        
        # 添加当前请求时间
        self.rate_limiter[ip].append(current_time)
        return False


def setup_security(app: FastAPI):
    """配置应用安全设置"""
    
    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://yourdomain.com"],  # 生产环境配置
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # 可信主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )
    
    # 自定义安全中间件
    app.add_middleware(SecurityMiddleware)
```

## 6. 使用示例

### 用户注册和登录
```python
from vprism.auth.authentication import auth_manager

# 用户注册
hashed_password = auth_manager.get_password_hash("user_password")

# 用户登录
token = auth_manager.create_access_token({"sub": str(user.id)})
```

### API端点保护
```python
from fastapi import Depends
from vprism.auth.authorization import RequireAdmin

@app.get("/admin/users", dependencies=[Depends(RequireAdmin)])
async def get_users():
    return {"users": []}
```

### API密钥认证
```python
from vprism.auth.authentication import get_api_key_user

@app.get("/api/data")
async def get_data(current_user: User = Depends(get_api_key_user)):
    return {"data": "protected_data"}
```

这个安全认证系统提供了：
- JWT令牌认证
- API密钥认证
- 基于RBAC的权限控制
- 完整的审计日志
- 数据加密存储
- 速率限制和DDoS防护
- 安全头部设置
- CORS配置