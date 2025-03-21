import json
from pydantic import Field,BaseModel
from gradio_ui.agent.base_agent import BaseAgent
from xbrain.core.chat import run

from gradio_ui.tools.computer import Action

class VerificationAgent(BaseAgent):
    def __call__(self, messages, parsed_screen_result):
        messages.append(
            {"role": "user", 
             "content": [
                {"type": "text", "text": "Image is the screenshot of the current screen"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{parsed_screen_result['base64_image']}"}
                }
             ]
             })
        response = run(
            messages, 
            user_prompt=prompt.format(screen_info=str(parsed_screen_result['parsed_content_list']), action_list=str(Action)), 
            response_format=VerificationResponse
        )
        return json.loads(response)

class VerificationResponse(BaseModel):
    verification_status: str = Field(description="验证状态", json_schema_extra={"enum": ["success", "error"]})
    verification_method: str = Field(description="验证方法")
    reasoning: str = Field(description="描述您验证的逻辑")
    failure_reason: str = Field(description="失败原因")
    remedy_measures: list[str] = Field(description="补救措施")

prompt = """
### 目标 ###
你是自动化验证专家，负责确认每个操作后的预期结果是否达成，保证自动化流程可靠执行。
以下是当前屏幕上的内容：
{screen_info}

### 输入 ###
1. 操作信息：刚执行的操作类型和参数
2. 屏幕状态：当前屏幕上的视觉元素和状态
3. 预期结果：操作应该产生的效果

### 输出格式 ###
验证结果应采用以下JSON格式：
{{
  "验证状态": "成功/失败",
  "验证方法": "使用的验证方法",
  "证据": "支持验证结果的具体证据",
  "失败原因": "如果失败，分析可能的原因",
  "补救措施": [
    "再执行一次操作"
  ],
}}

### 验证方法 ###
1. **视觉验证**：识别特定UI元素是否出现或消失
   - 元素存在性：检查某元素是否存在
   - 元素状态：检查元素是否处于特定状态（激活、禁用等）
   - 视觉变化：检查屏幕特定区域是否发生变化

2. **内容验证**：确认特定文本或数据是否正确
   - 文本匹配：页面上是否包含预期文本
   - 数据一致性：显示的数据是否符合预期
   - 计数验证：元素数量是否符合预期

3. **系统状态验证**：检查系统响应
   - 进程状态：特定进程是否运行
   - 文件变化：文件是否被创建、修改或删除
   - 网络活动：是否有特定网络请求或响应

### 验证策略 ###
- **重试机制**：指定最大重试次数和间隔时间
- **渐进式验证**：先验证基础条件，再验证详细条件
- **模糊匹配**：允许近似匹配而非精确匹配
- **超时设置**：指定验证的最长等待时间

### 补救措施 ###
补救措施建议如下：
- 【推荐】可以再等待一段时间看看效果，因为上一个操作还没执行完成就开始了验证
- 再一次操作
- 检查是否存在其他验证方法，但是仅限于以下几个动作：
{action_list}
### 例子 ###
操作：点击"登录"按钮
预期结果：登录成功并显示首页
验证输出：
{{
  "verification_status": "success",
  "verification_method": "视觉验证+内容验证",
  "reasoning": "1. 检测到欢迎消息'你好，用户名' 2. 导航栏显示用户头像 3. URL已变更为首页地址",
  "failure_reason": "无",
  "remedy_measures": [],
}}
"""
