import requests
import json
import os
import tempfile
import sys
import subprocess
import re
from requests.exceptions import ConnectionError, RequestException, Timeout
import time

def ensure_utf8_encoding(text):
    """确保文本是UTF-8编码"""
    if text is None:
        return None
    
    # 如果已经是utf-8字符串，直接返回
    if isinstance(text, str):
        try:
            # 尝试检测是否有乱码
            if any(ord(c) > 0xFFFF for c in text):
                # 可能有Unicode编码问题，尝试修复
                bytes_data = text.encode('latin1')
                return bytes_data.decode('utf-8')
            return text
        except (UnicodeEncodeError, UnicodeDecodeError):
            # 尝试修复编码
            try:
                # 如果是乱码，可能是编码错误，尝试解码为latin1再重新编码为utf-8
                bytes_data = text.encode('latin1')
                return bytes_data.decode('utf-8')
            except:
                return text  # 无法修复，返回原文本
    
    # 如果是bytes，尝试解码为utf-8
    if isinstance(text, bytes):
        try:
            return text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return text.decode('latin1')
            except:
                return str(text)  # 无法解码，返回字符串表示
    
    # 其他类型，转为字符串
    return str(text)

class OllamaAPI:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
    
    def list_models(self):
        """获取所有已安装的模型列表"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=3)
            if response.status_code == 200:
                return response.json().get('models', [])
            else:
                return []
        except (ConnectionError, Timeout) as e:
            print(f"获取模型列表失败，无法连接 (可能是安全模式阻止了网络): {e}")
            return []
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []
    
    def get_model_info(self, model_name):
        """获取特定模型的详细信息"""
        try:
            response = requests.post(
                f"{self.api_url}/show", 
                json={"name": model_name},
                timeout=3
            )
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except (ConnectionError, Timeout) as e:
            print(f"获取模型信息失败，无法连接 (可能是安全模式阻止了网络): {e}")
            return None
        except Exception as e:
            print(f"获取模型信息失败: {e}")
            return None
    
    def delete_model(self, model_name):
        """删除一个模型"""
        try:
            response = requests.delete(
                f"{self.api_url}/delete", 
                json={"name": model_name}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"删除模型失败: {e}")
            return False
    
    def pull_model(self, model_name):
        """下载一个模型"""
        try:
            response = requests.post(
                f"{self.api_url}/pull", 
                json={"name": model_name}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"拉取模型失败: {e}")
            return False
    
    def create_model(self, model_name, modelfile_content):
        """使用Modelfile创建一个新模型"""
        temp_file = None
        try:
            # 确保modelfile_content内容有效
            if not modelfile_content or not modelfile_content.strip().startswith("FROM"):
                print("无效的Modelfile内容，必须包含FROM指令")
                return False
            
            # 创建临时Modelfile，明确指定编码为UTF-8
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.modelfile') as f:
                f.write(modelfile_content)
                modelfile_path = f.name
                temp_file = f.name
            
            # 先检查模型是否已存在，如果存在则先备份
            existing_model = False
            try:
                result = subprocess.run(f'ollama list | findstr "{model_name}"', shell=True, capture_output=True, text=True)
                existing_model = model_name in result.stdout
            except:
                pass
            
            if existing_model:
                # 对于已存在的模型，使用不同的方法修改
                print(f"模型 {model_name} 已存在，进行修改")
                
                if sys.platform == 'win32':
                    # 创建一个临时名称
                    temp_model_name = f"{model_name}_temp_{int(time.time())}"
                    
                    # 首先使用临时名称创建新模型
                    cmd1 = f'ollama create {temp_model_name} -f "{modelfile_path}"'
                    result1 = subprocess.run(cmd1, shell=True, encoding='utf-8', capture_output=True)
                    
                    if result1.returncode != 0:
                        print(f"创建临时模型失败: {result1.stderr}")
                        return False
                    
                    # 删除原模型
                    cmd2 = f'ollama rm {model_name}'
                    result2 = subprocess.run(cmd2, shell=True, encoding='utf-8', capture_output=True)
                    
                    # 重命名临时模型
                    cmd3 = f'ollama cp {temp_model_name} {model_name}'
                    result3 = subprocess.run(cmd3, shell=True, encoding='utf-8', capture_output=True)
                    
                    # 删除临时模型
                    cmd4 = f'ollama rm {temp_model_name}'
                    subprocess.run(cmd4, shell=True, encoding='utf-8')
                    
                    success = result3.returncode == 0
                else:
                    # 非Windows系统
                    cmd = f'ollama create {model_name} -f "{modelfile_path}"'
                    result = subprocess.run(cmd, shell=True, encoding='utf-8', capture_output=True)
                    success = result.returncode == 0
            else:
                # 对于新模型，直接创建
                print(f"创建新模型: {model_name}")
                
                if sys.platform == 'win32':
                    cmd = f'ollama create {model_name} -f "{modelfile_path}"'
                    result = subprocess.run(cmd, shell=True, encoding='utf-8', capture_output=True)
                    
                    if result.returncode != 0:
                        print(f"创建模型失败: {result.stderr}")
                    
                    success = result.returncode == 0
                else:
                    # 其他系统使用系统命令
                    result = os.system(f'ollama create {model_name} -f "{modelfile_path}"')
                    success = result == 0
            
            # 删除临时文件
            if os.path.exists(modelfile_path):
                try:
                    os.unlink(modelfile_path)
                except Exception as e:
                    print(f"删除临时文件失败: {e}")
            
            # 验证模型是否创建成功
            if success:
                # 检查模型是否可用
                verify_cmd = f'ollama list | findstr "{model_name}"'
                verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)
                if model_name not in verify_result.stdout:
                    print(f"模型 {model_name} 创建失败，未出现在模型列表中")
                    success = False
            
            return success
        except Exception as e:
            print(f"创建模型失败: {e}")
            # 确保清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return False
    
    def get_modelfile(self, model_name):
        """获取模型的Modelfile内容"""
        try:
            info = self.get_model_info(model_name)
            if info and 'modelfile' in info:
                # 确保返回的内容是UTF-8编码
                modelfile_content = info['modelfile']
                return ensure_utf8_encoding(modelfile_content)
            return None
        except Exception as e:
            print(f"获取Modelfile失败: {e}")
            return None
    
    def check_connection(self):
        """检查与Ollama API的连接状态"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=2)
            return response.status_code == 200
        except (ConnectionError, Timeout):
            # 可能是安全模式阻止了网络连接
            return False
        except:
            return False
    
    @staticmethod
    def get_modelfile_template():
        """获取Modelfile的模板和参数说明"""
        template = """# Modelfile参数说明：
# FROM - 基础模型，如llama2, mistral, gemma等
# PARAMETER - 设置模型参数，如temperature, top_p等
# SYSTEM - 系统提示，定义模型的行为和角色
# TEMPLATE - 自定义提示模板格式
# ADAPTER - 指定adapter文件(适用于LoRA等微调)

FROM {{base_model}}

# 控制生成的随机性 (0.0-1.0)
PARAMETER temperature 0.7

# 控制生成多样性 (0.0-1.0)
PARAMETER top_p 0.9

# 控制结束生成的标记
# PARAMETER stop "User:"

# 系统提示，定义模型角色和行为
SYSTEM {{system_prompt}}
"""
        # 确保模板是UTF-8编码
        return ensure_utf8_encoding(template) 