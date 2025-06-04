#!/usr/bin/env python3
"""
快速诊断脚本

快速检查系统状态并提供修复建议
"""

import os
import sys
import sqlite3
import traceback
from typing import Dict, Any, List


def check_environment() -> Dict[str, Any]:
    """检查环境配置"""
    print("🔍 检查环境配置...")
    
    env_status = {
        'python_version': sys.version,
        'working_directory': os.getcwd(),
        'env_file_exists': os.path.exists('.env'),
        'openai_api_key': None,
        'use_local_embeddings': None,
        'local_embedding_path': None
    }
    
    # 检查环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        env_status['openai_api_key'] = os.getenv('OPENAI_API_KEY', 'Not set')
        env_status['use_local_embeddings'] = os.getenv('USE_LOCAL_EMBEDDINGS', 'Not set')
        env_status['local_embedding_path'] = os.getenv('LOCAL_EMBEDDING_MODEL_PATH', 'Not set')
        
        print(f"  ✅ Python版本: {sys.version.split()[0]}")
        print(f"  ✅ 工作目录: {os.getcwd()}")
        print(f"  {'✅' if env_status['env_file_exists'] else '❌'} .env文件: {'存在' if env_status['env_file_exists'] else '不存在'}")
        print(f"  ✅ OPENAI_API_KEY: {'已设置' if env_status['openai_api_key'] != 'Not set' else '未设置'}")
        print(f"  ✅ USE_LOCAL_EMBEDDINGS: {env_status['use_local_embeddings']}")
        
    except Exception as e:
        print(f"  ❌ 环境检查失败: {e}")
        env_status['error'] = str(e)
    
    return env_status


def check_database() -> Dict[str, Any]:
    """检查数据库状态"""
    print("\n🗄️ 检查数据库状态...")
    
    db_status = {
        'file_exists': False,
        'tables': [],
        'novel_count': 0,
        'character_count': 0,
        'chapter_count': 0,
        'issues': []
    }
    
    db_file = 'novel_mvp.db'
    
    try:
        db_status['file_exists'] = os.path.exists(db_file)
        
        if db_status['file_exists']:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            db_status['tables'] = [table[0] for table in tables]
            
            # 检查数据量
            if 'novels' in db_status['tables']:
                cursor.execute("SELECT COUNT(*) FROM novels")
                db_status['novel_count'] = cursor.fetchone()[0]
            
            if 'characters' in db_status['tables']:
                cursor.execute("SELECT COUNT(*) FROM characters")
                db_status['character_count'] = cursor.fetchone()[0]
            
            if 'chapters' in db_status['tables']:
                cursor.execute("SELECT COUNT(*) FROM chapters")
                db_status['chapter_count'] = cursor.fetchone()[0]
            
            conn.close()
            
            print(f"  ✅ 数据库文件存在")
            print(f"  ✅ 表数量: {len(db_status['tables'])}")
            print(f"  ✅ 小说数量: {db_status['novel_count']}")
            print(f"  ✅ 角色数量: {db_status['character_count']}")
            print(f"  ✅ 章节数量: {db_status['chapter_count']}")
            
        else:
            print(f"  ❌ 数据库文件不存在: {db_file}")
            db_status['issues'].append("数据库文件不存在")
            
    except Exception as e:
        print(f"  ❌ 数据库检查失败: {e}")
        db_status['issues'].append(f"数据库检查失败: {e}")
    
    return db_status


def check_chromadb() -> Dict[str, Any]:
    """检查ChromaDB状态"""
    print("\n🔮 检查ChromaDB状态...")
    
    chroma_status = {
        'directory_exists': False,
        'file_count': 0,
        'size_mb': 0,
        'can_import': False,
        'can_create_manager': False,
        'issues': []
    }
    
    chroma_dir = './chroma_db'
    
    try:
        # 检查目录
        chroma_status['directory_exists'] = os.path.exists(chroma_dir)
        
        if chroma_status['directory_exists']:
            for root, dirs, files in os.walk(chroma_dir):
                chroma_status['file_count'] += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    chroma_status['size_mb'] += os.path.getsize(file_path) / (1024 * 1024)
        
        # 测试导入
        try:
            from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
            chroma_status['can_import'] = True
            print(f"  ✅ 可以导入KnowledgeBaseManager")
        except Exception as e:
            chroma_status['can_import'] = False
            chroma_status['issues'].append(f"无法导入KnowledgeBaseManager: {e}")
            print(f"  ❌ 无法导入KnowledgeBaseManager: {e}")
        
        # 测试创建管理器
        if chroma_status['can_import']:
            try:
                kb_manager = KnowledgeBaseManager(db_directory=chroma_dir)
                chroma_status['can_create_manager'] = True
                print(f"  ✅ 可以创建KnowledgeBaseManager")
            except Exception as e:
                chroma_status['can_create_manager'] = False
                chroma_status['issues'].append(f"无法创建KnowledgeBaseManager: {e}")
                print(f"  ❌ 无法创建KnowledgeBaseManager: {e}")
        
        print(f"  {'✅' if chroma_status['directory_exists'] else '❌'} ChromaDB目录: {'存在' if chroma_status['directory_exists'] else '不存在'}")
        print(f"  ✅ 文件数量: {chroma_status['file_count']}")
        print(f"  ✅ 目录大小: {chroma_status['size_mb']:.2f} MB")
        
    except Exception as e:
        print(f"  ❌ ChromaDB检查失败: {e}")
        chroma_status['issues'].append(f"ChromaDB检查失败: {e}")
    
    return chroma_status


def test_workflow_components() -> Dict[str, Any]:
    """测试工作流组件"""
    print("\n⚙️ 测试工作流组件...")
    
    component_status = {
        'database_manager': False,
        'knowledge_base_manager': False,
        'lore_keeper_agent': False,
        'context_synthesizer_agent': False,
        'issues': []
    }
    
    # 测试DatabaseManager
    try:
        from src.persistence.database_manager import DatabaseManager
        db_manager = DatabaseManager()
        novels = db_manager.get_all_novels()
        component_status['database_manager'] = True
        print(f"  ✅ DatabaseManager正常 (找到 {len(novels)} 部小说)")
    except Exception as e:
        component_status['issues'].append(f"DatabaseManager失败: {e}")
        print(f"  ❌ DatabaseManager失败: {e}")
    
    # 测试KnowledgeBaseManager
    try:
        from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
        kb_manager = KnowledgeBaseManager()
        collections = kb_manager.list_collections()
        component_status['knowledge_base_manager'] = True
        print(f"  ✅ KnowledgeBaseManager正常 (找到 {len(collections)} 个集合)")
    except Exception as e:
        component_status['issues'].append(f"KnowledgeBaseManager失败: {e}")
        print(f"  ❌ KnowledgeBaseManager失败: {e}")
    
    # 测试LoreKeeperAgent
    try:
        from src.agents.lore_keeper_agent import LoreKeeperAgent
        # 不实际创建，只测试导入
        component_status['lore_keeper_agent'] = True
        print(f"  ✅ LoreKeeperAgent可以导入")
    except Exception as e:
        component_status['issues'].append(f"LoreKeeperAgent失败: {e}")
        print(f"  ❌ LoreKeeperAgent失败: {e}")
    
    # 测试ContextSynthesizerAgent
    try:
        from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
        # 不实际创建，只测试导入
        component_status['context_synthesizer_agent'] = True
        print(f"  ✅ ContextSynthesizerAgent可以导入")
    except Exception as e:
        component_status['issues'].append(f"ContextSynthesizerAgent失败: {e}")
        print(f"  ❌ ContextSynthesizerAgent失败: {e}")
    
    return component_status


def provide_recommendations(env_status: Dict, db_status: Dict, chroma_status: Dict, component_status: Dict) -> List[str]:
    """提供修复建议"""
    recommendations = []
    
    # 环境问题
    if not env_status.get('env_file_exists'):
        recommendations.append("创建.env文件并设置必要的环境变量")
    
    if env_status.get('openai_api_key') == 'Not set':
        recommendations.append("设置OPENAI_API_KEY环境变量")
    
    # 数据库问题
    if not db_status.get('file_exists'):
        recommendations.append("运行系统以创建数据库文件")
    
    if db_status.get('issues'):
        recommendations.append("修复数据库问题")
    
    # ChromaDB问题
    if chroma_status.get('issues'):
        recommendations.append("运行 'python fix_chromadb_issues.py' 修复ChromaDB问题")
    
    if not chroma_status.get('can_create_manager'):
        recommendations.append("清理ChromaDB目录并重新初始化")
    
    # 组件问题
    if component_status.get('issues'):
        recommendations.append("检查依赖包安装情况")
        recommendations.append("确保所有必要的Python包已正确安装")
    
    return recommendations


def main():
    """主函数"""
    print("🚀 小说生成系统快速诊断")
    print("=" * 50)
    
    try:
        # 执行各项检查
        env_status = check_environment()
        db_status = check_database()
        chroma_status = check_chromadb()
        component_status = test_workflow_components()
        
        # 汇总结果
        print("\n📊 诊断结果汇总")
        print("-" * 30)
        
        total_issues = (
            len(env_status.get('issues', [])) +
            len(db_status.get('issues', [])) +
            len(chroma_status.get('issues', [])) +
            len(component_status.get('issues', []))
        )
        
        if total_issues == 0:
            print("✅ 系统状态良好，没有发现问题")
        else:
            print(f"⚠️  发现 {total_issues} 个问题")
        
        # 提供建议
        recommendations = provide_recommendations(env_status, db_status, chroma_status, component_status)
        
        if recommendations:
            print("\n💡 修复建议")
            print("-" * 30)
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")
        
        print("\n🔧 快速修复命令")
        print("-" * 30)
        print("python fix_chromadb_issues.py  # 修复ChromaDB问题")
        print("python cleanup_memory_issues.py  # 清理记忆问题")
        print("python test_problem_solver.py  # 运行完整测试")
        
    except Exception as e:
        print(f"\n❌ 诊断过程中发生错误: {e}")
        print("\n🔍 详细错误信息:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
