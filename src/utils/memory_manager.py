"""
内存和知识库管理工具
用于解决人物记忆混杂和知识库清理问题
"""

from typing import List, Dict, Any, Optional
from src.persistence.database_manager import DatabaseManager
from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
import json


class MemoryManager:
    """管理小说生成过程中的记忆和知识库"""
    
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"):
        self.db_manager = DatabaseManager(db_name=db_name)
        self.kb_manager = KnowledgeBaseManager(db_directory=chroma_db_directory)
    
    def list_novels_with_stats(self) -> List[Dict[str, Any]]:
        """列出所有小说及其统计信息"""
        novels = self.db_manager.list_all_novels()
        novel_stats = []
        
        for novel in novels:
            novel_id = novel['id']
            characters = self.db_manager.get_characters_for_novel(novel_id)
            chapters = self.db_manager.get_chapters_for_novel(novel_id)
            kb_stats = self.kb_manager.get_collection_stats(novel_id)
            
            stats = {
                'novel_id': novel_id,
                'title': f"Novel {novel_id}",  # 可以从user_theme获取更好的标题
                'theme': novel.get('user_theme', 'Unknown'),
                'character_count': len(characters),
                'chapter_count': len(chapters),
                'kb_document_count': kb_stats.get('document_count', 0),
                'creation_date': novel.get('creation_date', 'Unknown'),
                'last_updated': novel.get('last_updated_date', 'Unknown')
            }
            novel_stats.append(stats)
        
        return novel_stats
    
    def get_novel_memory_details(self, novel_id: int) -> Dict[str, Any]:
        """获取指定小说的详细记忆信息"""
        novel = self.db_manager.get_novel_by_id(novel_id)
        if not novel:
            return {"error": f"Novel {novel_id} not found"}
        
        characters = self.db_manager.get_characters_for_novel(novel_id)
        chapters = self.db_manager.get_chapters_for_novel(novel_id)
        kb_entries = self.db_manager.get_kb_entries_for_novel(novel_id)
        kb_stats = self.kb_manager.get_collection_stats(novel_id)
        
        return {
            'novel_info': novel,
            'characters': [
                {
                    'id': char['character_id'],
                    'name': char['name'],
                    'role': char['role_in_story'],
                    'creation_date': char['creation_date']
                } for char in characters
            ],
            'chapters': [
                {
                    'id': chap['id'],
                    'number': chap['chapter_number'],
                    'title': chap['title'],
                    'creation_date': chap['creation_date']
                } for chap in chapters
            ],
            'knowledge_base': {
                'entry_count': len(kb_entries),
                'vector_document_count': kb_stats.get('document_count', 0),
                'collection_name': kb_stats.get('collection_name', ''),
                'entries_by_type': self._group_kb_entries_by_type(kb_entries)
            }
        }
    
    def _group_kb_entries_by_type(self, kb_entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """按类型分组知识库条目"""
        type_counts = {}
        for entry in kb_entries:
            entry_type = entry.get('entry_type', 'unknown')
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1
        return type_counts
    
    def clear_novel_memory(self, novel_id: int, clear_characters: bool = True, 
                          clear_chapters: bool = False, clear_knowledge_base: bool = True) -> Dict[str, Any]:
        """清除指定小说的记忆数据"""
        results = {
            'novel_id': novel_id,
            'operations': [],
            'success': True,
            'errors': []
        }
        
        try:
            # 清除角色数据
            if clear_characters:
                success = self.db_manager.clear_characters_for_novel(novel_id)
                results['operations'].append({
                    'operation': 'clear_characters',
                    'success': success
                })
                if not success:
                    results['errors'].append('Failed to clear characters')
                    results['success'] = False
            
            # 清除章节数据（谨慎操作）
            if clear_chapters:
                chapters = self.db_manager.get_chapters_for_novel(novel_id)
                for chapter in chapters:
                    # 这里可以添加更细粒度的删除逻辑
                    pass
                results['operations'].append({
                    'operation': 'clear_chapters',
                    'success': True,
                    'note': 'Chapter clearing not implemented for safety'
                })
            
            # 清除知识库
            if clear_knowledge_base:
                success = self.kb_manager.clear_knowledge_base(novel_id)
                results['operations'].append({
                    'operation': 'clear_knowledge_base',
                    'success': success
                })
                if not success:
                    results['errors'].append('Failed to clear knowledge base')
                    results['success'] = False
            
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"Unexpected error: {str(e)}")
        
        return results
    
    def delete_specific_character(self, character_id: int) -> bool:
        """删除指定的角色"""
        return self.db_manager.delete_character(character_id)
    
    def update_character_info(self, character_id: int, name: str = None, 
                            description: str = None, role_in_story: str = None) -> bool:
        """更新角色信息"""
        return self.db_manager.update_character(character_id, name, description, role_in_story)
    
    def export_novel_memory(self, novel_id: int) -> Dict[str, Any]:
        """导出小说的记忆数据（用于备份）"""
        details = self.get_novel_memory_details(novel_id)
        if 'error' in details:
            return details
        
        # 获取完整的角色信息
        full_characters = self.db_manager.get_characters_for_novel(novel_id)
        full_chapters = self.db_manager.get_chapters_for_novel(novel_id)
        kb_entries = self.db_manager.get_kb_entries_for_novel(novel_id)
        
        export_data = {
            'novel_info': details['novel_info'],
            'characters': full_characters,
            'chapters': full_chapters,
            'knowledge_base_entries': kb_entries,
            'export_timestamp': self._get_current_timestamp()
        }
        
        return export_data
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    def get_memory_isolation_report(self) -> Dict[str, Any]:
        """生成记忆隔离报告，检查是否存在跨小说的数据泄露"""
        novels = self.db_manager.list_all_novels()
        report = {
            'total_novels': len(novels),
            'novels': [],
            'potential_issues': [],
            'recommendations': []
        }
        
        character_names_by_novel = {}
        all_character_names = []
        
        for novel in novels:
            novel_id = novel['id']
            characters = self.db_manager.get_characters_for_novel(novel_id)
            character_names = [char['name'] for char in characters]
            character_names_by_novel[novel_id] = character_names
            all_character_names.extend(character_names)
            
            novel_report = {
                'novel_id': novel_id,
                'theme': novel.get('user_theme', 'Unknown'),
                'character_count': len(characters),
                'character_names': character_names
            }
            report['novels'].append(novel_report)
        
        # 检查重复的角色名称
        name_counts = {}
        for name in all_character_names:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        duplicate_names = {name: count for name, count in name_counts.items() if count > 1}
        if duplicate_names:
            report['potential_issues'].append({
                'type': 'duplicate_character_names',
                'details': duplicate_names,
                'description': '发现重复的角色名称，可能导致记忆混杂'
            })
            report['recommendations'].append('考虑为重复的角色名称添加小说标识符或重命名')
        
        # 检查知识库集合
        collections = self.kb_manager.list_collections()
        report['knowledge_base_collections'] = collections
        
        if len(collections) != len(novels):
            report['potential_issues'].append({
                'type': 'kb_collection_mismatch',
                'details': f'知识库集合数量({len(collections)})与小说数量({len(novels)})不匹配',
                'description': '知识库集合与小说数量不匹配'
            })
            report['recommendations'].append('检查并清理无用的知识库集合')
        
        return report


if __name__ == "__main__":
    print("--- Testing MemoryManager ---")
    
    # 创建测试实例
    memory_manager = MemoryManager()
    
    # 列出所有小说
    print("\n=== 小说列表 ===")
    novels = memory_manager.list_novels_with_stats()
    for novel in novels:
        print(f"小说 {novel['novel_id']}: {novel['theme']} - {novel['character_count']} 角色, {novel['chapter_count']} 章节")
    
    # 生成记忆隔离报告
    print("\n=== 记忆隔离报告 ===")
    report = memory_manager.get_memory_isolation_report()
    print(f"总小说数: {report['total_novels']}")
    
    if report['potential_issues']:
        print("发现的问题:")
        for issue in report['potential_issues']:
            print(f"  - {issue['type']}: {issue['description']}")
    else:
        print("未发现记忆隔离问题")
    
    if report['recommendations']:
        print("建议:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
    
    print("\n--- MemoryManager Test Finished ---")
