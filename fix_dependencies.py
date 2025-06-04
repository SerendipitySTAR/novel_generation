#!/usr/bin/env python3
"""
依赖修复脚本
检查并安装缺失的依赖包
"""

import subprocess
import sys
import os
import importlib

def check_package(package_name, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

def install_package(package_name):
    """安装包"""
    print(f"正在安装 {package_name}...")
    try:
        # 尝试使用conda安装（如果在conda环境中）
        if 'CONDA_DEFAULT_ENV' in os.environ:
            try:
                result = subprocess.run([
                    'conda', 'install', '-y', package_name
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    print(f"✅ 通过conda成功安装 {package_name}")
                    return True
                else:
                    print(f"⚠️  conda安装失败，尝试pip安装...")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                print(f"⚠️  conda不可用，尝试pip安装...")
        
        # 使用pip安装
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', package_name
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ 通过pip成功安装 {package_name}")
            return True
        else:
            print(f"❌ 安装失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ 安装超时: {package_name}")
        return False
    except Exception as e:
        print(f"❌ 安装出错: {e}")
        return False

def main():
    """主函数"""
    print("🔍 检查依赖包...")
    
    # 定义需要检查的包
    required_packages = [
        ('sentence-transformers', 'sentence_transformers'),
        ('langchain', 'langchain'),
        ('langchain-community', 'langchain_community'),
        ('chromadb', 'chromadb'),
        ('openai', 'openai'),
        ('python-dotenv', 'dotenv'),
    ]
    
    missing_packages = []
    
    # 检查每个包
    for package_name, import_name in required_packages:
        if check_package(package_name, import_name):
            print(f"✅ {package_name} 已安装")
        else:
            print(f"❌ {package_name} 未安装")
            missing_packages.append(package_name)
    
    if not missing_packages:
        print("\n🎉 所有依赖包都已安装！")
        return True
    
    print(f"\n📦 发现 {len(missing_packages)} 个缺失的包:")
    for pkg in missing_packages:
        print(f"  - {pkg}")
    
    # 询问是否安装
    response = input("\n是否自动安装缺失的包? (Y/n): ").strip().lower()
    if response == 'n':
        print("跳过安装。请手动安装缺失的包。")
        return False
    
    # 安装缺失的包
    print("\n🔧 开始安装缺失的包...")
    success_count = 0
    
    for package_name in missing_packages:
        if install_package(package_name):
            success_count += 1
        else:
            print(f"⚠️  {package_name} 安装失败")
    
    print(f"\n📊 安装结果: {success_count}/{len(missing_packages)} 个包安装成功")
    
    if success_count == len(missing_packages):
        print("🎉 所有包都安装成功！")
        
        # 验证安装
        print("\n🔍 验证安装...")
        all_ok = True
        for package_name, import_name in required_packages:
            if check_package(package_name, import_name):
                print(f"✅ {package_name} 验证通过")
            else:
                print(f"❌ {package_name} 验证失败")
                all_ok = False
        
        if all_ok:
            print("\n🎉 所有依赖都已正确安装！")
            return True
        else:
            print("\n⚠️  部分依赖验证失败，可能需要重启Python环境")
            return False
    else:
        print("\n⚠️  部分包安装失败，请检查错误信息并手动安装")
        return False

def test_knowledge_base():
    """测试知识库功能"""
    print("\n🧪 测试知识库功能...")
    
    try:
        # 测试导入
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        print("✅ 成功导入知识库相关模块")
        
        # 测试本地嵌入模型路径
        local_model_path = "/media/sc/AI/self-llm/embed_model/sentence-transformers/all-MiniLM-L6-v2"
        if os.path.exists(local_model_path):
            print(f"✅ 本地嵌入模型路径存在: {local_model_path}")
            
            # 尝试初始化嵌入模型
            try:
                embeddings = HuggingFaceEmbeddings(
                    model_name=local_model_path,
                    model_kwargs={'device': 'cpu'}
                )
                print("✅ 成功初始化本地嵌入模型")
                
                # 测试嵌入
                test_text = "这是一个测试文本"
                embedding = embeddings.embed_query(test_text)
                print(f"✅ 成功生成嵌入向量 (维度: {len(embedding)})")
                
                return True
                
            except Exception as e:
                print(f"❌ 嵌入模型初始化失败: {e}")
                return False
        else:
            print(f"⚠️  本地嵌入模型路径不存在: {local_model_path}")
            print("   将回退到OpenAI嵌入")
            return True
            
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def create_env_template():
    """创建环境变量模板"""
    env_template = """# 小说生成系统环境变量配置

# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here

# 本地模型配置
USE_LOCAL_EMBEDDINGS=true
LOCAL_EMBEDDING_MODEL_PATH=/media/sc/AI/self-llm/embed_model/sentence-transformers/all-MiniLM-L6-v2

# 数据库配置
DATABASE_NAME=novel_mvp.db
CHROMA_DB_DIRECTORY=./chroma_db

# 其他配置
DEBUG=false
"""
    
    if not os.path.exists('.env'):
        print("\n📝 创建环境变量模板文件...")
        with open('.env.template', 'w', encoding='utf-8') as f:
            f.write(env_template)
        print("✅ 已创建 .env.template 文件")
        print("   请复制为 .env 并填入正确的配置值")
    else:
        print("✅ .env 文件已存在")

if __name__ == "__main__":
    print("🔧 小说生成系统依赖修复工具")
    print("=" * 50)
    
    # 切换到正确目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    # 检查并安装依赖
    deps_ok = main()
    
    if deps_ok:
        # 测试知识库功能
        kb_ok = test_knowledge_base()
        
        if kb_ok:
            print("\n🎉 所有功能测试通过！")
        else:
            print("\n⚠️  知识库功能测试失败，但基本依赖已安装")
    
    # 创建环境变量模板
    create_env_template()
    
    print("\n📋 下一步建议:")
    if deps_ok:
        print("  1. ✅ 依赖已安装，可以运行系统")
        print("  2. 🔧 如果仍有问题，请重启Python环境")
        print("  3. 📝 检查 .env 文件配置")
    else:
        print("  1. ❌ 请手动安装失败的依赖包")
        print("  2. 🔍 检查网络连接和包管理器配置")
        print("  3. 📞 如需帮助，请查看错误信息")
    
    print("\n测试命令:")
    print("  python3 test_problem_solver.py")
    print("  python3 cleanup_memory_issues.py")
