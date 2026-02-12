#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代码完整性测试脚本
用于验证 flai_agent 项目的主要组件是否正常工作
"""

import sys
import os
import ast

def test_syntax():
    """测试所有Python文件的语法"""
    print("🔍 检查代码语法...")
    
    # 获取所有Python文件
    py_files = []
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in root or '.venv' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    
    print(f"找到 {len(py_files)} 个Python文件")
    
    errors = []
    for file_path in py_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            # 只显示部分路径以避免输出过长
            rel_path = os.path.relpath(file_path, os.getcwd())
            print(f"  ✅ {rel_path}")
        except SyntaxError as e:
            rel_path = os.path.relpath(file_path, os.getcwd())
            print(f"  ❌ {rel_path}: 语法错误 (第{e.lineno}行)")
            errors.append((file_path, str(e)))
        except UnicodeDecodeError:
            # 忽略非文本文件
            continue
        except Exception as e:
            rel_path = os.path.relpath(file_path, os.getcwd())
            print(f"  ⚠️  {rel_path}: 读取错误")
    
    if errors:
        print(f"\n⚠️  发现 {len(errors)} 个语法错误")
    else:
        print("\n✅ 所有文件语法正确")
    
    assert not errors, f"发现 {len(errors)} 个语法错误"

def test_imports():
    """测试关键模块导入"""
    print("\n🔍 测试模块导入...")
    
    modules_to_test = [
        ('src.main', 'app'),
        ('src.api.routes', 'router'),
        ('src.services.chat_service', 'ChatService'),
        ('src.services.llm_service', 'LLMService'),
        ('src.services.memory_service', 'MemoryService'),
        ('src.core.config_loader', 'get_config_loader'),
        ('src.core.content_filter', 'ContentFilter'),
        ('src.schemas', None),
        ('src.utils', None),
        ('src.custom_logger', 'custom_logger'),
        ('src.database', 'engine'),
    ]
    
    failed_imports = []
    
    for module_path, attr in modules_to_test:
        try:
            if attr:
                exec(f"from {module_path} import {attr}")
                print(f"  ✅ {module_path}.{attr}")
            else:
                exec(f"import {module_path}")
                print(f"  ✅ {module_path}")
        except ImportError as e:
            print(f"  ❌ {module_path}: 导入错误 - {e}")
            failed_imports.append((module_path, str(e)))
        except Exception as e:
            print(f"  ❌ {module_path}: 其他错误 - {e}")
            failed_imports.append((module_path, str(e)))
    
    if failed_imports:
        print(f"\n⚠️  发现 {len(failed_imports)} 个导入错误")
    else:
        print("\n✅ 所有关键模块导入成功")
    
    assert not failed_imports, f"发现 {len(failed_imports)} 个导入错误"

def test_config():
    """测试配置加载"""
    print("\n🔍 测试配置加载...")
    
    try:
        from src.core.config_loader import get_config_loader
        config_loader = get_config_loader()
        
        # 测试加载各种配置
        chars = config_loader.get_characters()
        openers = config_loader.get_character_openers()
        emotions = config_loader.get_emotion_states()
        responses = config_loader.get_responses()
        constants = config_loader.get_constants()
        
        print(f"  ✅ 加载了 {len(chars)} 个角色")
        print(f"  ✅ 加载了 {len(openers)} 个开场白配置")
        print(f"  ✅ 加载了 {len(emotions)} 个情绪状态")
        print(f"  ✅ 加载了响应和常量配置")
        
    except Exception as e:
        print(f"  ❌ 配置加载错误: {e}")
        assert False, f"配置加载错误: {e}"

def main():
    """主测试函数"""
    print("🧪 开始测试 flai_agent 项目代码完整性...\n")
    
    results = []
    
    # 运行各项测试
    try:
        test_syntax()
        results.append(("语法检查", True))
    except Exception as e:
        print(f"  ❌ 语法检查失败: {e}")
        results.append(("语法检查", False))
        
    try:
        test_imports()
        results.append(("模块导入", True))
    except Exception as e:
        print(f"  ❌ 模块导入失败: {e}")
        results.append(("模块导入", False))
        
    try:
        test_config()
        results.append(("配置加载", True))
    except Exception as e:
        print(f"  ❌ 配置加载失败: {e}")
        results.append(("配置加载", False))
    
    # 输出总结
    print(f"\n📊 测试结果汇总:")
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📈 总体结果: {passed}/{len(results)} 项测试通过")
    
    if passed == len(results):
        print("🎉 项目代码完整性检查通过！")
        print("✅ 代码没有语法错误")
        print("✅ 所有关键模块可以正常导入")
        print("✅ 配置文件可以正常加载")
        return True
    else:
        print("⚠️  项目存在一些问题需要修复")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)