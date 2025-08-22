"""定义多智能体系统的可配置参数。"""

from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Optional, Dict, Any
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModelConfig:
    """语言模型配置。"""
    
    main_model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}]
    classification_model: str


@dataclass(kw_only=True)
class ElasticsearchConfig:
    """Elasticsearch 连接与索引配置。"""
    
    host: str
    username: Optional[str]
    password: Optional[str]
    artwork_index: str
    
    def __post_init__(self):
        """校验配置。"""
        if not self.host.startswith(('http://', 'https://')):
            raise ValueError("Elasticsearch host must start with http:// or https://")
    

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> "ElasticsearchConfig":
        """从 JSON 字典创建配置（可选字段）。"""
        host = data.get("host", "http://localhost:9200")
        username = (data.get("username") or "").strip() or None
        password = (data.get("password") or "").strip() or None
        artwork_index = data.get("artwork_index", "artwork_info_816")
        return cls(host=host, username=username, password=password, artwork_index=artwork_index)


@dataclass(kw_only=True)
class MCPConfig:
    """MCP（Model Context Protocol）服务器配置。"""
    
    servers: Dict[str, Dict[str, Any]]
    

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """基于 servers_config.json 结构从 JSON 字典创建配置。"""
        raw_servers: Dict[str, Dict[str, Any]] = data.get("mcpServers", {}) or {}
        normalized: Dict[str, Dict[str, Any]] = {}
        for name, cfg in raw_servers.items():
            cfg_copy = dict(cfg)
            normalized[name] = cfg_copy
        return cls(servers=normalized)

@dataclass(kw_only=True)
class Configuration:
    """多智能体系统主配置。"""

    model_config: ModelConfig
    elasticsearch_config: ElasticsearchConfig
    mcp_config: MCPConfig
    
    def __post_init__(self):
        """初始化校验。"""
        logger.info("Configuration loaded successfully")
    
    # INI loading has been removed. Use load_from_json() instead.

    @staticmethod
    def _substitute_env_vars(content: str) -> str:
        """在 JSON 字符串中用环境变量替换 ${VAR}。"""
        pattern = r"\$\{([^}]+)\}"
        def replacer(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.getenv(var, "")
        return re.sub(pattern, replacer, content)

    @classmethod
    def load_from_json(cls, config_path: Optional[str] = None) -> "Configuration":
        """从 servers_config.json（或同结构文件）加载配置。

        支持的键：
        - models: { main_model, classification_model }
        - elasticsearch: { host, username, password, artwork_index }
        - mcpServers: { ... }
        """
        if config_path is None:
            possible_paths = [
                Path(__file__).parent / "servers_config.json",
                Path.cwd() / "servers_config.json",
            ]
            found_path: Optional[Path] = None
            for path in possible_paths:
                if path.exists():
                    found_path = path
                    break
            if found_path is None:
                raise FileNotFoundError("servers_config.json not found. Please create one based on servers_config.json.example")
            config_path = str(found_path)

        with open(config_path, "r", encoding="utf-8") as f:
            raw = f.read()
        substituted = cls._substitute_env_vars(raw)
        data: Dict[str, Any] = json.loads(substituted)
        logger.info(f"Configuration loaded from JSON: {config_path}")

        # Load models
        models_data = data.get("models", {}) or {}
        model_config = ModelConfig(
            main_model=models_data.get("main_model", "openrouter/anthropic/claude-sonnet-4"),
            classification_model=models_data.get("classification_model", "openrouter/openai/gpt-4.1-mini"),
        )

        # Load Elasticsearch
        es_data = data.get("elasticsearch", {}) or {}
        elasticsearch_config = ElasticsearchConfig.from_json_dict(es_data)

        # Load MCP servers
        mcp_config = MCPConfig.from_json_dict(data)

        return cls(
            model_config=model_config,
            elasticsearch_config=elasticsearch_config,
            mcp_config=mcp_config,
        )
    
    @property
    def model(self) -> str:
        """主模型（向后兼容属性）。"""
        return self.model_config.main_model
    
    @property  
    def classification_model(self) -> str:
        """分类模型（向后兼容属性）。"""
        return self.model_config.classification_model
    
    @property
    def elasticsearch_host(self) -> str:
        """Elasticsearch 主机地址（向后兼容属性）。"""
        return self.elasticsearch_config.host
    
    @property
    def elasticsearch_username(self) -> Optional[str]:
        """Elasticsearch 用户名（向后兼容属性）。"""
        return self.elasticsearch_config.username
    
    @property
    def elasticsearch_password(self) -> Optional[str]:
        """Elasticsearch 密码（向后兼容属性）。"""
        return self.elasticsearch_config.password
    
    @property
    def elasticsearch_index_artwork(self) -> str:
        """艺术作品索引名（向后兼容属性）。"""
        return self.elasticsearch_config.artwork_index
    
    @property
    def mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """返回适用于 MCP 客户端的服务器映射。"""
        return self.mcp_config.servers

    @classmethod
    def from_context(cls) -> Configuration:
        """从运行上下文创建 `Configuration` 实例。"""
        return get_configuration()


@lru_cache()
def get_configuration() -> Configuration:
    """获取缓存的配置实例。"""
    return Configuration.load_from_json()