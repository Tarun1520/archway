"""
The language-model adapter: one small interface, several implementations.

    base.py      the interface every model client follows (LLMClient)
    fixture.py   a stand-in that answers from simple rules: free, offline
    groq.py      the real client for Groq's API
    factory.py   picks one of the two from the settings

The rest of the app only knows `LLMClient`. To add another provider, write
one new file with the same method and add one line to factory.py.

Learn more: LEARNING_GUIDE.md topics 23 and 31.
"""
