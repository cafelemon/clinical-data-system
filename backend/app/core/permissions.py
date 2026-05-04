from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionSpec:
    code: str
    label: str
    module: str
    description: str = ""


PERMISSIONS = [
    PermissionSpec("master_data:read", "查看主数据", "master_data"),
    PermissionSpec("master_data:write", "维护主数据", "master_data"),
    PermissionSpec("dictionaries:read", "查看状态字典", "dictionaries"),
    PermissionSpec("dictionaries:write", "维护状态字典", "dictionaries"),
    PermissionSpec("users:read", "查看用户", "identity"),
    PermissionSpec("users:write", "维护用户", "identity"),
    PermissionSpec("roles:read", "查看角色", "identity"),
    PermissionSpec("roles:write", "维护角色", "identity"),
    PermissionSpec("permissions:read", "查看权限", "identity"),
    PermissionSpec("clinical_data:read", "查看临床数据集", "clinical_data"),
    PermissionSpec("clinical_data:write", "维护临床数据集", "clinical_data"),
]

ROLE_SPECS = {
    "admin": {
        "label": "管理员",
        "description": "系统全局管理",
        "permissions": [permission.code for permission in PERMISSIONS],
    },
    "project_manager": {
        "label": "项目负责人",
        "description": "管理指定项目",
        "permissions": [
            "master_data:read",
            "master_data:write",
            "dictionaries:read",
            "clinical_data:read",
            "clinical_data:write",
        ],
    },
    "center_manager": {
        "label": "中心负责人",
        "description": "管理指定中心",
        "permissions": [
            "master_data:read",
            "dictionaries:read",
            "clinical_data:read",
            "clinical_data:write",
        ],
    },
    "clinical_coordinator": {
        "label": "临床协调员",
        "description": "上传和维护资料",
        "permissions": [
            "master_data:read",
            "dictionaries:read",
            "clinical_data:read",
            "clinical_data:write",
        ],
    },
    "reviewer": {
        "label": "审核人员",
        "description": "审核文件和数据项",
        "permissions": ["master_data:read", "dictionaries:read", "clinical_data:read"],
    },
    "rd_user": {
        "label": "研发人员",
        "description": "查看临床数据、访问研发数据模块",
        "permissions": ["master_data:read", "dictionaries:read", "clinical_data:read"],
    },
    "readonly": {
        "label": "只读用户",
        "description": "只读查看",
        "permissions": ["master_data:read", "dictionaries:read", "clinical_data:read"],
    },
}
