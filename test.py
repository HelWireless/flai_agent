import byzerllm

data = {
    'name': 'Jane Doe',
    'task_count': 3,
    'tasks': [
        {'name': 'Submit report', 'due_date': '2024-03-10'},
        {'name': 'Finish project', 'due_date': '2024-03-15'},
        {'name': 'Reply to emails', 'due_date': '2024-03-08'}
    ]
}


class RAG():
    def __init__(self):
        self.llm = byzerllm.ByzerLLM()
        self.llm.setup_template(model="deepseek_chat", template="auto")
        self.llm.setup_default_model_name("deepseek_chat")

    @byzerllm.prompt(lambda self: self.llm)
    def generate_answer(self, name, task_count, tasks) -> str:
        '''
        Hello {{ name }},

        This is a reminder that you have {{ task_count }} pending tasks:
        {% for task in tasks %}
        - Task: {{ task.name }} | Due: {{ task.due_date }}
        {% endfor %}

        Best regards,
        Your Reminder System
        '''


t = RAG()

response = t.generate_answer(**data)
print(response)