"""
Offline Content Generator — produces realistic, domain-aware curriculum content
without any API calls. Used as a guaranteed fallback for presentations.

Generates: week skeleton, section content, resources, and practice questions
based on the learner's domain (JavaScript, Python, C++, React, etc.)
"""

from __future__ import annotations
import re

# ─────────────────────────────────────────────────────────────────────────────
# Domain knowledge base — realistic curricula for common domains
# ─────────────────────────────────────────────────────────────────────────────

CURRICULA: dict[str, list[dict]] = {
    "javascript": [
        {"week_title": "JavaScript Foundations", "week_objective": "Understand how JavaScript works in the browser and write your first interactive programs.", "sections": ["How the Web Works & Browser Dev Tools", "Variables, Data Types & Operators", "Control Flow: if/else & switch", "Loops: for, while & do-while", "Functions & Scope"]},
        {"week_title": "Arrays, Objects & DOM", "week_objective": "Master JavaScript's core data structures and manipulate HTML elements programmatically.", "sections": ["Arrays & Array Methods", "Objects & Destructuring", "DOM Selection & Manipulation", "Event Listeners & Handlers", "Form Handling & Validation"]},
        {"week_title": "Asynchronous JavaScript", "week_objective": "Handle async operations confidently using callbacks, Promises, and async/await.", "sections": ["Callbacks & the Event Loop", "Promises & .then() Chaining", "async/await Syntax", "Fetch API & REST Calls", "Error Handling with try/catch"]},
        {"week_title": "ES6+ Modern JavaScript", "week_objective": "Write cleaner, more expressive code using modern ES6+ features.", "sections": ["Arrow Functions & Template Literals", "Spread, Rest & Destructuring", "Modules: import & export", "Classes & Prototypes", "Map, Set & WeakMap"]},
    ],
    "python": [
        {"week_title": "Python Fundamentals", "week_objective": "Set up Python and write your first programs using variables, control flow, and functions.", "sections": ["Python Setup & the REPL", "Variables, Types & Type Casting", "Strings & String Methods", "Control Flow: if/elif/else", "Loops: for & while"]},
        {"week_title": "Functions & Data Structures", "week_objective": "Write reusable functions and master Python's built-in data structures.", "sections": ["Defining & Calling Functions", "Lists & List Comprehensions", "Dictionaries & Sets", "Tuples & Unpacking", "Lambda, map & filter"]},
        {"week_title": "Object-Oriented Python", "week_objective": "Apply OOP principles to build modular, maintainable Python programs.", "sections": ["Classes & Objects", "Inheritance & Polymorphism", "Magic Methods (__init__, __str__)", "Decorators & Property", "Modules & Packages"]},
        {"week_title": "File I/O & Libraries", "week_objective": "Read/write files and use Python's powerful standard library and third-party packages.", "sections": ["File Reading & Writing", "JSON & CSV Handling", "Error Handling & Exceptions", "Virtual Environments & pip", "Intro to NumPy / Pandas"]},
    ],
    "react": [
        {"week_title": "React Fundamentals", "week_objective": "Understand React's component model and build your first UI with JSX and props.", "sections": ["What is React & JSX Syntax", "Functional Components & Props", "useState Hook", "Conditional Rendering", "Lists & Keys"]},
        {"week_title": "State Management & Effects", "week_objective": "Manage component state and side-effects using React hooks.", "sections": ["useEffect & Lifecycle", "useRef & DOM Access", "Lifting State Up", "Context API & useContext", "Custom Hooks"]},
        {"week_title": "Routing & Forms", "week_objective": "Build multi-page apps with React Router and handle complex form state.", "sections": ["React Router v6 Setup", "Dynamic Routes & Params", "Controlled vs Uncontrolled Forms", "Form Validation Patterns", "useReducer for Complex State"]},
        {"week_title": "Performance & Deployment", "week_objective": "Optimize your React app and deploy it to production.", "sections": ["useMemo & useCallback", "Code Splitting & Lazy Loading", "React.memo & Performance", "Building & Vite Config", "Deployment to Vercel / Netlify"]},
    ],
    "cpp": [
        {"week_title": "C++ Fundamentals", "week_objective": "Understand C++ syntax, compile your first program, and work with variables and basic I/O.", "sections": ["Introduction to C++ & Compilation", "Variables, Data Types & Keywords", "Identifiers & Operators", "Loops: for, while & do-while", "Functions & Parameters"]},
        {"week_title": "Arrays, Pointers & Memory", "week_objective": "Master C++ memory model, pointers, and low-level data structures.", "sections": ["Arrays & Multi-dimensional Arrays", "Pointers & Address-of Operator", "References vs Pointers", "Dynamic Memory: new & delete", "Strings: char[] vs std::string"]},
        {"week_title": "Object-Oriented C++", "week_objective": "Apply OOP principles: encapsulation, inheritance, and polymorphism in C++.", "sections": ["Classes & Objects", "Constructors & Destructors", "Inheritance & Access Specifiers", "Polymorphism & Virtual Functions", "Operator Overloading"]},
        {"week_title": "STL & Modern C++", "week_objective": "Use the Standard Template Library and modern C++11/17 features effectively.", "sections": ["Vectors, Lists & Deques", "Maps, Sets & Iterators", "Lambda Expressions", "Smart Pointers (unique_ptr, shared_ptr)", "Templates & Generic Programming"]},
    ],
}

# Section-specific content database
SECTION_CONTENT: dict[str, dict] = {
    "how the web works": {
        "explanation": "The web operates on a client-server model. When you type a URL, your browser (client) sends an HTTP request to a server. The server responds with HTML, CSS, and JavaScript files that the browser parses and renders into a visual page. Understanding this flow — DNS lookup → TCP connection → HTTP request/response → DOM construction — is foundational to everything you'll build as a web developer. Modern browsers expose DevTools to inspect this entire process in real time.",
        "code_example": {"language": "javascript", "code": "// Open DevTools (F12) → Network tab\n// Then run this to make a real HTTP request:\nfetch('https://jsonplaceholder.typicode.com/todos/1')\n  .then(res => res.json())\n  .then(data => console.log(data))\n  // Output: { userId: 1, id: 1, title: '...', completed: false }", "caption": "Using fetch() to make an HTTP GET request — visible in the Network tab"},
        "resources": [{"title": "How the Web Works — MDN", "url": "https://developer.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web/How_the_Web_works", "type": "documentation"}, {"title": "HTTP Crash Course — Traversy Media", "url": "https://www.youtube.com/watch?v=iYM2zFP3Zn0", "type": "video", "duration_minutes": 37}],
        "practice": [{"question": "Open your browser's DevTools (F12), go to the Network tab, and visit any website. Identify: (1) the first request made, (2) the response status code, and (3) the content-type header. Write a short paragraph explaining what you observed.", "type": "written", "difficulty": "easy"}],
    },
    "variables, data types & operators": {
        "explanation": "JavaScript is dynamically typed — you don't declare what type a variable holds, the engine figures it out at runtime. Use `const` for values that won't be reassigned, `let` for values that will change, and avoid `var` (function-scoped, causes subtle bugs). The 7 primitive types are: string, number, bigint, boolean, undefined, null, and symbol. The `typeof` operator lets you inspect a value's type at runtime. Understanding type coercion (how JS converts types automatically) is critical to avoiding hard-to-debug bugs.",
        "code_example": {"language": "javascript", "code": "const name = 'Alice'       // string\nlet age = 25               // number\nconst isStudent = true     // boolean\nlet score                  // undefined (declared, not assigned)\n\n// Type checking\nconsole.log(typeof name)   // 'string'\nconsole.log(typeof age)    // 'number'\n\n// Type coercion trap!\nconsole.log('5' + 3)       // '53'  (string concat)\nconsole.log('5' - 3)       // 2     (numeric subtraction)\nconsole.log(Boolean(''))   // false (falsy value)", "caption": "Variable declaration, types, and the coercion trap every JS dev must know"},
        "resources": [{"title": "JavaScript Data Types — MDN", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Data_structures", "type": "documentation"}, {"title": "JavaScript Variables — javascript.info", "url": "https://javascript.info/variables", "type": "article"}],
        "practice": [{"question": "Write a JavaScript snippet that declares 5 variables (string, number, boolean, null, undefined). Use console.log(typeof ...) to print each type. Then try adding a string to a number and explain the result.", "type": "written", "difficulty": "easy"}],
    },
    "functions & parameters": {
        "explanation": "Functions are the primary building blocks of any JavaScript program — they let you group logic, name it, and reuse it. A function declaration is hoisted (available before its definition in code), while a function expression is not. Parameters are the variable names in the definition; arguments are the actual values passed when calling. Default parameters allow you to specify fallback values. Understanding scope — what variables a function can access — is critical: functions create their own scope, and closures let inner functions 'remember' their outer environment even after the outer function has returned.",
        "code_example": {"language": "javascript", "code": "// Function declaration (hoisted)\nfunction greet(name = 'stranger') {\n  return `Hello, ${name}!`\n}\n\n// Function expression (not hoisted)\nconst add = function(a, b) {\n  return a + b\n}\n\n// Closure example — inner fn remembers outer scope\nfunction makeCounter() {\n  let count = 0\n  return function() {\n    count++\n    return count\n  }\n}\n\nconst counter = makeCounter()\nconsole.log(counter()) // 1\nconsole.log(counter()) // 2\nconsole.log(counter()) // 3", "caption": "Function declaration, expression, default params, and a real closure"},
        "resources": [{"title": "Functions — MDN", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions", "type": "documentation"}, {"title": "JavaScript Functions — javascript.info", "url": "https://javascript.info/function-basics", "type": "article"}],
        "practice": [{"question": "Write a function `calculateGrade(score)` that takes a number 0–100 and returns 'A' (90+), 'B' (80+), 'C' (70+), 'D' (60+), or 'F'. Then write a closure-based function `makeMultiplier(factor)` that returns a function multiplying any number by that factor.", "type": "written", "difficulty": "medium"}],
    },
}

# Generic resource templates by domain
RESOURCES_BY_DOMAIN: dict[str, list[dict]] = {
    "javascript": [
        {"title": "JavaScript Guide — MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "type": "documentation"},
        {"title": "The Modern JavaScript Tutorial", "url": "https://javascript.info", "type": "tutorial"},
        {"title": "JavaScript Full Course — Dave Gray", "url": "https://www.youtube.com/watch?v=EfAl9bwzVZk", "type": "video", "duration_minutes": 180},
    ],
    "python": [
        {"title": "Python Official Documentation", "url": "https://docs.python.org/3/", "type": "documentation"},
        {"title": "Python Tutorial — W3Schools", "url": "https://www.w3schools.com/python/", "type": "tutorial"},
        {"title": "Python for Beginners — Mosh Hamedani", "url": "https://www.youtube.com/watch?v=kqtD5dpn9C8", "type": "video", "duration_minutes": 48},
    ],
    "react": [
        {"title": "React Official Docs", "url": "https://react.dev", "type": "documentation"},
        {"title": "React Full Course — Scrimba", "url": "https://scrimba.com/learn/learnreact", "type": "tutorial"},
        {"title": "React Hooks Explained — Fireship", "url": "https://www.youtube.com/watch?v=TNhaISOUy6Q", "type": "video", "duration_minutes": 11},
    ],
    "cpp": [
        {"title": "C++ Tutorial — cplusplus.com", "url": "https://cplusplus.com/doc/tutorial/", "type": "documentation"},
        {"title": "C++ Reference — cppreference.com", "url": "https://cppreference.com", "type": "documentation"},
        {"title": "C++ Full Course — The Cherno", "url": "https://www.youtube.com/playlist?list=PLlrATfBNZ98dudnM48yfGUldqGD0S4FFb", "type": "video", "duration_minutes": 60},
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _detect_domain_key(domain: str) -> str:
    """Map free-text domain to our knowledge base key."""
    d = domain.lower()
    if any(k in d for k in ["react", "next", "vue", "angular"]): return "react"
    if any(k in d for k in ["python", "django", "flask", "fastapi"]): return "python"
    if any(k in d for k in ["c++", "cpp"]): return "cpp"
    return "javascript"  # default


def generate_offline_roadmap(domain: str, knowledge_level: str, duration_weeks: int, goal: str) -> dict:
    """
    Generate a full roadmap skeleton offline — no API needed.
    Returns the standard { weeks: [...] } structure with section titles only.
    """
    key = _detect_domain_key(domain)
    curriculum = CURRICULA.get(key, CURRICULA["javascript"])

    weeks = []
    for i in range(min(duration_weeks, max(len(curriculum), 4))):
        template = curriculum[i % len(curriculum)]
        sections = [
            {"section_number": j + 1, "section_title": title}
            for j, title in enumerate(template["sections"])
        ]
        weeks.append({
            "week_number": i + 1,
            "week_title": template["week_title"],
            "week_objective": template["week_objective"],
            "what_user_should_know_after": [
                f"Understand {template['sections'][0]}",
                f"Apply {template['sections'][1]} in real code",
                f"Build confidence with {template['sections'][-1]}",
            ],
            "status": "active" if i == 0 else "pending",
            "sections": sections,
        })

    return {"weeks": weeks}


def generate_offline_week_content(week: dict, domain: str, knowledge_level: str) -> dict:
    """
    Fill in content/resources/practice for all sections in a week — offline.
    """
    key = _detect_domain_key(domain)
    default_resources = RESOURCES_BY_DOMAIN.get(key, RESOURCES_BY_DOMAIN["javascript"])
    sections = week.get("sections", [])

    for s_idx, section in enumerate(sections):
        title = section.get("section_title", "")
        # Try to find pre-written content for this section
        content_key = title.lower()
        pre = None
        for k, v in SECTION_CONTENT.items():
            if k in content_key or content_key in k:
                pre = v
                break

        if pre:
            section["content"] = {
                "explanation": pre["explanation"],
                "code_example": pre.get("code_example"),
            }
            section["resources"] = pre.get("resources", default_resources[:2])
            section["practice"] = pre.get("practice", [])
        else:
            # Generate generic but domain-specific content
            section["content"] = {
                "explanation": (
                    f"{title} is a core concept in {domain} that every developer must understand deeply. "
                    f"At the {knowledge_level} level, your goal is to move beyond surface definitions — "
                    f"focus on understanding *why* this exists, *when* to use it, and what trade-offs it involves. "
                    f"Real-world applications of {title} appear frequently in production code, interviews, and system design. "
                    f"Work through the examples below carefully, then complete the practice task before moving on."
                ),
                "code_example": _generate_code_example(title, key),
            }
            section["resources"] = default_resources[:2]
            section["practice"] = [{
                "question": f"Write a short program (10–20 lines) that demonstrates your understanding of {title}. Include a comment explaining what each key line does.",
                "type": "written",
                "difficulty": "easy" if s_idx == 0 else "medium",
            }]

    return week


def _generate_code_example(title: str, domain_key: str) -> dict | None:
    """Generate a minimal but realistic code example for a section."""
    t = title.lower()
    lang_map = {"javascript": "javascript", "react": "jsx", "python": "python", "cpp": "cpp"}
    lang = lang_map.get(domain_key, "javascript")

    if "loop" in t:
        if domain_key == "python":
            return {"language": "python", "code": "# for loop\nfor i in range(1, 11):\n    print(f'Count: {i}')\n\n# while loop\nn = 5\nwhile n > 0:\n    print(n)\n    n -= 1", "caption": "for and while loops in Python"}
        return {"language": "javascript", "code": "// for loop\nfor (let i = 1; i <= 10; i++) {\n  console.log(`Count: ${i}`)\n}\n\n// while loop\nlet n = 5\nwhile (n > 0) {\n  console.log(n)\n  n--\n}", "caption": "for and while loops in JavaScript"}

    if "array" in t or "list" in t:
        if domain_key == "python":
            return {"language": "python", "code": "fruits = ['apple', 'banana', 'cherry']\n\n# Access\nprint(fruits[0])      # apple\n\n# List methods\nfruits.append('date')\nfruits.remove('banana')\n\n# List comprehension\nsquares = [x**2 for x in range(5)]\nprint(squares)        # [0, 1, 4, 9, 16]", "caption": "Python lists — creation, methods, and comprehensions"}
        return {"language": "javascript", "code": "const fruits = ['apple', 'banana', 'cherry']\n\n// Access & mutate\nconsole.log(fruits[0])          // 'apple'\nfruits.push('date')\nfruits.splice(1, 1)             // remove banana\n\n// Functional methods\nconst upper = fruits.map(f => f.toUpperCase())\nconst long  = fruits.filter(f => f.length > 5)\nconsole.log(upper, long)", "caption": "JavaScript arrays — access, mutation, and functional methods"}

    if "class" in t or "object" in t:
        if domain_key in ("cpp", "c++"):
            return {"language": "cpp", "code": "#include <iostream>\n#include <string>\nusing namespace std;\n\nclass Student {\nprivate:\n    string name;\n    int age;\npublic:\n    Student(string n, int a) : name(n), age(a) {}\n    void display() {\n        cout << name << \" (\" << age << \")\" << endl;\n    }\n};\n\nint main() {\n    Student s(\"Alice\", 21);\n    s.display();\n    return 0;\n}", "caption": "A C++ class with a constructor and member function"}
        if domain_key == "python":
            return {"language": "python", "code": "class Student:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n\n    def greet(self):\n        return f'Hi, I am {self.name}, age {self.age}'\n\n    def __repr__(self):\n        return f'Student({self.name!r}, {self.age})'\n\nstudent = Student('Alice', 21)\nprint(student.greet())\nprint(student)", "caption": "Python class with __init__, instance methods, and __repr__"}

    return None
