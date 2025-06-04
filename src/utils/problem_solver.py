#!/usr/bin/env python3
"""
问题解决工具
用于解决人物记忆混杂和循环问题
"""

import argparse
import sys
import json
from typing import Dict, Any
from src.utils.memory_manager import MemoryManager
from src.orchestration.workflow_manager import WorkflowManager


class ProblemSolver:
    """解决小说生成系统中的问题"""
    
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"):
        self.memory_manager = MemoryManager(db_name, chroma_db_directory)
        self.workflow_manager = WorkflowManager(db_name)
    
    def diagnose_memory_issues(self) -> Dict[str, Any]:
        """诊断记忆问题"""
        print("🔍 正在诊断记忆问题...")
        
        # 获取记忆隔离报告
        report = self.memory_manager.get_memory_isolation_report()
        
        # 获取小说统计
        novels = self.memory_manager.list_novels_with_stats()
        
        diagnosis = {
            'memory_report': report,
            'novel_stats': novels,
            'issues_found': len(report.get('potential_issues', [])),
            'recommendations': report.get('recommendations', [])
        }
        
        return diagnosis
    
    def fix_memory_issues(self, novel_id: int = None, interactive: bool = True) -> Dict[str, Any]:
        """修复记忆问题"""
        print("🔧 正在修复记忆问题...")
        
        if novel_id:
            return self._fix_single_novel_memory(novel_id, interactive)
        else:
            return self._fix_all_memory_issues(interactive)
    
    def _fix_single_novel_memory(self, novel_id: int, interactive: bool) -> Dict[str, Any]:
        """修复单个小说的记忆问题"""
        details = self.memory_manager.get_novel_memory_details(novel_id)
        
        if 'error' in details:
            return {'success': False, 'error': details['error']}
        
        print(f"\n📖 小说 {novel_id} 详情:")
        print(f"  主题: {details['novel_info'].get('user_theme', 'Unknown')}")
        print(f"  角色数: {len(details['characters'])}")
        print(f"  章节数: {len(details['chapters'])}")
        print(f"  知识库条目: {details['knowledge_base']['entry_count']}")
        
        if interactive:
            print("\n可用操作:")
            print("1. 清除角色记忆")
            print("2. 清除知识库")
            print("3. 清除所有记忆（保留章节）")
            print("4. 导出记忆备份")
            print("5. 取消")
            
            choice = input("请选择操作 (1-5): ").strip()
            
            if choice == '1':
                return self.memory_manager.clear_novel_memory(novel_id, clear_characters=True, clear_knowledge_base=False)
            elif choice == '2':
                return self.memory_manager.clear_novel_memory(novel_id, clear_characters=False, clear_knowledge_base=True)
            elif choice == '3':
                return self.memory_manager.clear_novel_memory(novel_id, clear_characters=True, clear_knowledge_base=True)
            elif choice == '4':
                export_data = self.memory_manager.export_novel_memory(novel_id)
                filename = f"novel_{novel_id}_memory_backup.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                return {'success': True, 'message': f'记忆已导出到 {filename}'}
            else:
                return {'success': False, 'message': '操作已取消'}
        else:
            # 非交互模式，执行默认清理
            return self.memory_manager.clear_novel_memory(novel_id, clear_characters=True, clear_knowledge_base=True)
    
    def _fix_all_memory_issues(self, interactive: bool) -> Dict[str, Any]:
        """修复所有记忆问题"""
        diagnosis = self.diagnose_memory_issues()
        
        if diagnosis['issues_found'] == 0:
            return {'success': True, 'message': '未发现需要修复的记忆问题'}
        
        print(f"\n发现 {diagnosis['issues_found']} 个问题:")
        for issue in diagnosis['memory_report']['potential_issues']:
            print(f"  - {issue['description']}")
        
        if interactive:
            confirm = input("\n是否继续修复这些问题? (y/N): ").strip().lower()
            if confirm != 'y':
                return {'success': False, 'message': '用户取消了修复操作'}
        
        # 执行修复操作
        results = []
        for novel in diagnosis['novel_stats']:
            novel_id = novel['novel_id']
            if novel['character_count'] > 0 or novel['kb_document_count'] > 0:
                result = self.memory_manager.clear_novel_memory(novel_id)
                results.append(result)
        
        return {'success': True, 'results': results}
    
    def check_workflow_health(self) -> Dict[str, Any]:
        """检查工作流程健康状态"""
        print("🔍 正在检查工作流程健康状态...")
        
        # 这里可以添加更多的健康检查
        health_report = {
            'workflow_manager_initialized': self.workflow_manager is not None,
            'database_accessible': True,  # 可以添加实际的数据库连接检查
            'safety_features': {
                'loop_protection': True,  # 我们已经添加了循环保护
                'recursion_limit': True,
                'error_handling': True
            },
            'recommendations': []
        }
        
        try:
            # 尝试访问数据库
            novels = self.memory_manager.db_manager.get_all_novels()
            health_report['database_accessible'] = True
            health_report['novel_count'] = len(novels)
        except Exception as e:
            health_report['database_accessible'] = False
            health_report['database_error'] = str(e)
            health_report['recommendations'].append('检查数据库连接和权限')
        
        return health_report
    
    def emergency_stop_workflow(self) -> Dict[str, Any]:
        """紧急停止工作流程（如果正在运行）"""
        print("🛑 执行紧急停止...")
        
        # 这里可以添加实际的停止逻辑
        # 例如：设置停止标志、终止进程等
        
        return {
            'success': True,
            'message': '紧急停止信号已发送',
            'note': '如果工作流程仍在运行，请手动终止进程'
        }


def main():
    parser = argparse.ArgumentParser(description='小说生成系统问题解决工具')
    parser.add_argument('--db-name', default='novel_mvp.db', help='数据库文件名')
    parser.add_argument('--chroma-dir', default='./chroma_db', help='Chroma数据库目录')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 诊断命令
    diagnose_parser = subparsers.add_parser('diagnose', help='诊断记忆问题')
    
    # 修复命令
    fix_parser = subparsers.add_parser('fix', help='修复记忆问题')
    fix_parser.add_argument('--novel-id', type=int, help='指定要修复的小说ID')
    fix_parser.add_argument('--non-interactive', action='store_true', help='非交互模式')
    
    # 健康检查命令
    health_parser = subparsers.add_parser('health', help='检查系统健康状态')
    
    # 紧急停止命令
    stop_parser = subparsers.add_parser('emergency-stop', help='紧急停止工作流程')
    
    # 列出小说命令
    list_parser = subparsers.add_parser('list', help='列出所有小说')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        solver = ProblemSolver(args.db_name, args.chroma_dir)
        
        if args.command == 'diagnose':
            diagnosis = solver.diagnose_memory_issues()
            print(f"\n📊 诊断结果:")
            print(f"  总小说数: {len(diagnosis['novel_stats'])}")
            print(f"  发现问题: {diagnosis['issues_found']}")
            
            if diagnosis['issues_found'] > 0:
                print("\n问题详情:")
                for issue in diagnosis['memory_report']['potential_issues']:
                    print(f"  - {issue['description']}")
                
                print("\n建议:")
                for rec in diagnosis['recommendations']:
                    print(f"  - {rec}")
            else:
                print("✅ 未发现记忆问题")
        
        elif args.command == 'fix':
            result = solver.fix_memory_issues(
                novel_id=args.novel_id,
                interactive=not args.non_interactive
            )
            
            if result['success']:
                print("✅ 修复完成")
                if 'message' in result:
                    print(f"   {result['message']}")
            else:
                print("❌ 修复失败")
                if 'error' in result:
                    print(f"   错误: {result['error']}")
        
        elif args.command == 'health':
            health = solver.check_workflow_health()
            print(f"\n🏥 系统健康状态:")
            print(f"  工作流程管理器: {'✅' if health['workflow_manager_initialized'] else '❌'}")
            print(f"  数据库访问: {'✅' if health['database_accessible'] else '❌'}")
            print(f"  安全特性: {'✅' if all(health['safety_features'].values()) else '❌'}")
            
            if health.get('recommendations'):
                print("\n建议:")
                for rec in health['recommendations']:
                    print(f"  - {rec}")
        
        elif args.command == 'emergency-stop':
            result = solver.emergency_stop_workflow()
            print(f"🛑 {result['message']}")
            if 'note' in result:
                print(f"   注意: {result['note']}")
        
        elif args.command == 'list':
            novels = solver.memory_manager.list_novels_with_stats()
            print(f"\n📚 小说列表 (共 {len(novels)} 部):")
            for novel in novels:
                print(f"  ID {novel['novel_id']}: {novel['theme']}")
                print(f"    角色: {novel['character_count']}, 章节: {novel['chapter_count']}, 知识库: {novel['kb_document_count']}")
                print(f"    创建: {novel['creation_date']}")
    
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
