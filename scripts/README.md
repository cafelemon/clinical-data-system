# 脚本目录

用于存放初始化脚本、备份脚本、数据导入导出脚本和运维辅助工具。

## P8 备份脚本

数据库备份：

```bash
scripts/backup_database.sh
```

文件目录备份：

```bash
scripts/backup_files.sh
```

数据库恢复需要显式确认：

```bash
CONFIRM_RESTORE=yes scripts/restore_database.sh backups/db/clinical_data_YYYYmmdd_HHMMSS.sql
```

可用环境变量：

- `BACKUP_ROOT`：备份输出根目录，默认 `backups`
- `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`：PostgreSQL 连接参数
- `FILE_STORAGE_ROOT`：文件存储目录，默认 `data-dev/file-storage`
