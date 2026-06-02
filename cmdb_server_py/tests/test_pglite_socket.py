#!/usr/bin/env python3
"""py-pglite Socket 连接测试脚本

用于诊断和修复 py-pglite 的 socket 权限问题。

问题排查步骤：
1. 检查 socket 文件权限
2. 检查目录权限
3. 启动 py-pglite server
4. 测试连接
5. 测试读写操作
"""

import os
import sys
import time
import subprocess
import socket
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置
PROJECT_ROOT = '/workspace/bk_cmdb_py'
PGLITE_DATA_DIR = os.path.join(PROJECT_ROOT, 'pglite_data')
SOCKET_NAME = '.s.PGSQL.5432'
SOCKET_PATH = os.path.join(PGLITE_DATA_DIR, SOCKET_NAME)


def print_section(title):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def check_permissions():
    """检查文件和目录权限"""
    print_section("1. 权限检查")
    
    # 检查目录权限
    print(f"\n目录: {PGLITE_DATA_DIR}")
    if os.path.exists(PGLITE_DATA_DIR):
        stat_info = os.stat(PGLITE_DATA_DIR)
        mode = oct(stat_info.st_mode)[-3:]
        print(f"  权限: {mode}")
        print(f"  所有者: UID={stat_info.st_uid}, GID={stat_info.st_gid}")
        print(f"  ✅ 目录存在")
    else:
        print(f"  ❌ 目录不存在，尝试创建...")
        os.makedirs(PGLITE_DATA_DIR, mode=0o777, exist_ok=True)
        print(f"  ✅ 目录已创建")
    
    # 检查 socket 文件
    print(f"\nSocket 文件: {SOCKET_PATH}")
    if os.path.exists(SOCKET_PATH):
        stat_info = os.stat(SOCKET_PATH)
        mode = oct(stat_info.st_mode)[-3:]
        print(f"  权限: {mode}")
        print(f"  类型: {'Socket' if os.path.exists(SOCKET_PATH) else 'Unknown'}")
        
        # 检查是否是 socket
        import stat
        if stat.S_ISSOCK(stat_info.st_mode):
            print(f"  ✅ 是有效的 Socket 文件")
        else:
            print(f"  ⚠️  不是 socket 文件，可能是普通文件")
    else:
        print(f"  ❌ Socket 文件不存在（尚未启动 server）")


def fix_permissions():
    """修复权限问题"""
    print_section("2. 修复权限")
    
    # 设置目录权限为 777
    print(f"\n设置目录权限为 777...")
    try:
        os.chmod(PGLITE_DATA_DIR, 0o777)
        print(f"  ✅ 目录权限已设置为 777")
    except Exception as e:
        print(f"  ❌ 设置目录权限失败: {e}")
        return False
    
    # 如果 socket 存在，设置权限
    if os.path.exists(SOCKET_PATH):
        try:
            os.chmod(SOCKET_PATH, 0o777)
            print(f"  ✅ Socket 文件权限已设置为 777")
        except Exception as e:
            print(f"  ❌ 设置 socket 权限失败: {e}")
            return False
    
    return True


def start_pglite_server():
    """启动 py-pglite server"""
    print_section("3. 启动 PGlite Server")
    
    # 检查 node 进程是否在运行
    print("\n检查现有 node 进程...")
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'pglite_manager.js'],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"  发现 {len(pids)} 个 PGlite 进程:")
            for pid in pids:
                print(f"    - PID: {pid}")
            
            print("\n停止现有进程...")
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                    print(f"    ✅ 已终止 PID {pid}")
                except:
                    pass
            time.sleep(2)
    except Exception as e:
        print(f"  检查进程时出错: {e}")
    
    # 启动新的 server
    print(f"\n启动 PGlite Server...")
    print(f"  工作目录: {PGLITE_DATA_DIR}")
    print(f"  启动命令: node pglite_manager.js")
    
    env = os.environ.copy()
    env['NODE_PATH'] = f'{PGLITE_DATA_DIR}/node_modules'
    env['PGLITE_DATA_DIR'] = PGLITE_DATA_DIR
    
    try:
        # 启动进程
        process = subprocess.Popen(
            ['node', 'pglite_manager.js'],
            cwd=PGLITE_DATA_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print(f"\n  等待 Server 启动...")
        print(f"  PID: {process.pid}")
        
        # 等待 socket 文件出现或超时
        for i in range(30):
            if os.path.exists(SOCKET_PATH):
                print(f"  ✅ Socket 文件已创建 (等待 {i+1} 秒)")
                break
            time.sleep(1)
            if i % 5 == 0:
                print(f"  等待中... ({i+1}/30)")
        else:
            print(f"  ❌ Socket 文件超时未创建")
            print(f"\n  Server 输出:")
            try:
                stdout, _ = process.communicate(timeout=1)
                print(stdout)
            except:
                pass
            return None
        
        # 设置 socket 权限
        time.sleep(1)
        os.chmod(SOCKET_PATH, 0o777)
        print(f"  ✅ Socket 权限已设置为 777")
        
        # 读取启动日志
        print(f"\n  Server 启动日志:")
        try:
            stdout, _ = process.communicate(timeout=1)
            if stdout:
                print(stdout)
        except:
            pass
        
        return process
        
    except Exception as e:
        print(f"  ❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_connection():
    """测试数据库连接"""
    print_section("4. 测试数据库连接")
    
    import psycopg
    
    print(f"\n尝试连接到 PGlite...")
    print(f"  Host: {PGLITE_DATA_DIR}")
    print(f"  Socket: {SOCKET_PATH}")
    
    # 检查 socket 是否存在
    if not os.path.exists(SOCKET_PATH):
        print(f"  ❌ Socket 文件不存在")
        return False
    
    # 尝试连接 - 多种方法
    methods = [
        ("方法1: psycopg3 host参数 + user=postgres", lambda: __import__('psycopg').connect(
            host=PGLITE_DATA_DIR,
            dbname='postgres',
            user='postgres'
        )),
        ("方法2: psycopg3 conninfo字符串", lambda: __import__('psycopg').connect(
            f"host={PGLITE_DATA_DIR} dbname=postgres user=postgres"
        )),
        ("方法3: psycopg2 unix socket", lambda: __import__('psycopg2').connect(
            host=PGLITE_DATA_DIR,
            database='postgres',
            user='postgres'
        )),
        ("方法4: psycopg2 conninfo", lambda: __import__('psycopg2').connect(
            f"host={PGLITE_DATA_DIR} dbname=postgres user=postgres"
        )),
    ]
    
    for name, connect_func in methods:
        try:
            print(f"\n{name}...")
            conn = connect_func()
            print(f"  ✅ 连接成功!")
            conn.close()
            return True
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    return False


def test_read_write():
    """测试数据库读写操作"""
    print_section("5. 测试数据库读写操作")
    
    import psycopg
    
    try:
        # 连接
        print("\n建立连接...")
        import psycopg2
        conn = psycopg2.connect(
            host=PGLITE_DATA_DIR,
            database='postgres',
            user='postgres'
        )
        cur = conn.cursor()
        
        # 测试1: 创建表
        print("\n测试1: 创建表...")
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print(f"  ✅ 表创建成功")
        except Exception as e:
            print(f"  ❌ 创建表失败: {e}")
            return False
        
        # 测试2: 插入数据
        print("\n测试2: 插入数据...")
        try:
            cur.execute("""
                INSERT INTO test_table (name) VALUES (%s)
                RETURNING id, name
            """, ('Test User',))
            result = cur.fetchone()
            conn.commit()
            print(f"  ✅ 插入成功: id={result[0]}, name={result[1]}")
        except Exception as e:
            print(f"  ❌ 插入失败: {e}")
            return False
        
        # 测试3: 查询数据
        print("\n测试3: 查询数据...")
        try:
            cur.execute("SELECT id, name, created_at FROM test_table ORDER BY id DESC LIMIT 5")
            rows = cur.fetchall()
            print(f"  ✅ 查询成功，返回 {len(rows)} 条记录:")
            for row in rows:
                print(f"    - ID: {row[0]}, Name: {row[1]}, Created: {row[2]}")
        except Exception as e:
            print(f"  ❌ 查询失败: {e}")
            return False
        
        # 测试4: 更新数据
        print("\n测试4: 更新数据...")
        try:
            cur.execute("UPDATE test_table SET name = %s WHERE name = %s", ('Updated User', 'Test User'))
            conn.commit()
            print(f"  ✅ 更新成功，受影响行数: {cur.rowcount}")
        except Exception as e:
            print(f"  ❌ 更新失败: {e}")
            return False
        
        # 测试5: 删除数据
        print("\n测试5: 删除数据...")
        try:
            cur.execute("DELETE FROM test_table WHERE name = %s", ('Updated User',))
            conn.commit()
            print(f"  ✅ 删除成功，受影响行数: {cur.rowcount}")
        except Exception as e:
            print(f"  ❌ 删除失败: {e}")
            return False
        
        # 清理
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sqlalchemy():
    """测试 SQLAlchemy 连接"""
    print_section("6. 测试 SQLAlchemy 连接")
    
    from sqlalchemy import create_engine, text
    
    try:
        print("\n创建 SQLAlchemy Engine...")
        
        def get_connection():
            import psycopg
            return psycopg.connect(
                host=PGLITE_DATA_DIR,
                dbname='postgres',
                user='postgres',
                password='',
                autocommit=True
            )
        
        engine = create_engine(
            f"postgresql+psycopg://",
            creator=get_connection,
            echo=True
        )
        
        print("  ✅ Engine 创建成功")
        
        # 测试查询
        print("\n执行测试查询...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"  ✅ PostgreSQL 版本: {version[:50]}...")
            
            # 创建测试表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sqlalchemy_test (
                    id SERIAL PRIMARY KEY,
                    data TEXT
                )
            """))
            
            # 插入
            conn.execute(text("INSERT INTO sqlalchemy_test (data) VALUES (:data)"), {"data": "Hello from SQLAlchemy!"})
            
            # 查询
            result = conn.execute(text("SELECT * FROM sqlalchemy_test"))
            rows = result.fetchall()
            print(f"  ✅ 读写测试成功，返回 {len(rows)} 行")
        
        return True
        
    except Exception as e:
        print(f"  ❌ SQLAlchemy 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  py-pglite Socket 连接诊断工具")
    print("="*60)
    
    # 1. 检查权限
    check_permissions()
    
    # 2. 修复权限
    fix_permissions()
    
    # 3. 启动 server
    server_process = start_pglite_server()
    
    if not server_process:
        print("\n❌ Server 启动失败，无法继续测试")
        return 1
    
    # 4. 测试连接
    if not test_connection():
        print("\n❌ 连接测试失败")
        return 1
    
    # 5. 测试读写
    if not test_read_write():
        print("\n❌ 读写测试失败")
        return 1
    
    # 6. 测试 SQLAlchemy
    if not test_sqlalchemy():
        print("\n❌ SQLAlchemy 测试失败")
        return 1
    
    # 汇总
    print_section("诊断结果")
    print("\n✅ 所有测试通过!")
    print(f"\n配置建议:")
    print(f"  PGLITE_DATA_DIR={PGLITE_DATA_DIR}")
    print(f"  Socket 路径: {SOCKET_PATH}")
    print(f"  目录权限: 777")
    print(f"  Socket 权限: 777")
    
    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
