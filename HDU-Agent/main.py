# main.py
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.Agent.manager.graph import app


def main():
    print("🚀 Manager Agent 交互终端已启动！(输入 'quit' 退出)\n" + "-" * 40)

    # 维护一个全局对话历史，充当短期记忆
    chat_history = []

    while True:
        # 1. 获取用户持续输入
        user_input = input("\n🧑‍💻 用户: ")
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 测试结束，再见！")
            break

        if not user_input.strip():
            continue

        # 将用户新消息加入历史记录
        chat_history.append(("user", user_input))

        # 构造图的初始输入
        inputs = {
            "messages": chat_history
        }

        print("⏳ Agent 思考中...\n")

        try:
            # 2. 运行图
            for output in app.stream(inputs):
                for node_name, node_state in output.items():
                    # 只有 Manager 节点的回复我们才直接打印给用户看
                    if node_name == "manager":
                        latest_message = node_state['messages'][-1]

                        # 兼容处理：LangGraph 返回的可能是元组，也可能是 AIMessage 对象
                        content = latest_message.content if hasattr(latest_message, 'content') else latest_message[1]
                        print(f"🤖 [Manager]:\n{content}")

                        # 把 Agent 的回复也加入本地记忆，这样它就能记住上下文
                        chat_history.append(("assistant", content))
                        print("-" * 40)

                    elif node_name == "pentest_agent":
                        print(f"⚡ [系统提示]: 子智能体 pentest_agent 执行完毕，正在将报告回传给队长...")
                        # 子智能体产生的隐式对话（汇报结果）也存入历史，作为下一次 Manager 思考的依据
                        latest_message = node_state['messages'][-1]
                        content = latest_message.content if hasattr(latest_message, 'content') else latest_message[1]
                        chat_history.append(("user", content))

        except Exception as e:
            print(f"\n❌ 运行出错：{e}")


if __name__ == "__main__":
    main()