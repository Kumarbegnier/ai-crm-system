import { useState, useEffect, useRef } from "react";
import "./App.css";

let typingInterval = null;

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [ws, setWs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dark, setDark] = useState(false);

  const chatBoxRef = useRef(null);
  const isUserNearBottom = useRef(true);
  const chatEndRef = useRef(null);

  useEffect(() => {
    document.body.className = dark ? "dark" : "";

    const saved = localStorage.getItem("chat");
    if (saved) setMessages(JSON.parse(saved));
  }, []);

  useEffect(() => {
    localStorage.setItem("chat", JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    const socket = new WebSocket("ws://127.0.0.1:8000/ws");

    socket.onmessage = (event) => {
      const text = event.data;

      setMessages((prev) => {
        const last = prev[prev.length -1];

        if (last && last.role === "ai") {
          let currentText = last.text;
          let index = 0;

          clearInterval(typingInterval);
          typingInterval = setInterval(() => {
            if (index < text.length) {
              currentText += text[index];

              setMessages((prev2) => {
                const updated = [...prev2];
                updated[updated.length -1] = {
                  ...updated[updated.length -1],
                  text: currentText,
                };
                return updated;
              });

              index++;
            } else {
              clearInterval(typingInterval);
            }
          }, 10);

          return prev;
        }

        return [...prev, { role: "ai", text: "" }];
      });
    };

    setWs(socket);

    return () => socket.close();
  }, []);

  const handleScroll = () => {
    const el = chatBoxRef.current;

    const threshold = 100;
    const isNearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold;

    isUserNearBottom.current = isNearBottom;
  };

  useEffect(() => {
    if (isUserNearBottom.current) {
      chatBoxRef.current.scrollTo({
        top: chatBoxRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const sendMessage = () => {
    if (!input.trim()) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", text: input },
      { role: "ai", text: "" }
    ]);

    setLoading(true);

    ws.send(input);
    setInput("");
  };

  return (
    <div className="chat-container">
      <h1>AI HCP CRM</h1>
      <button onClick={() => setDark(!dark)}>Toggle Dark</button>

      <div 
        className="chat-box"
        ref={chatBoxRef}
        onScroll={handleScroll}
      >
        {messages.map((msg, i) => {
          const prev = messages[i - 1];

          const showAvatar = !prev || prev.role !== msg.role;

          return (
            <div
              key={i}
              className={msg.role === "user" ? "msg user" : "msg ai"}
            >
              {showAvatar && (
                <span className="avatar">
                  {msg.role === "user" ? "👤" : "🤖"}
                </span>
              )}
              <div className="bubble">
                {msg.text}
                <small>{new Date().toLocaleTimeString()}</small>
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="msg ai">
            <span className="avatar">🤖</span>
            <div className="bubble typing">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        {!isUserNearBottom.current && (
          <button
            className="scroll-btn"
            onClick={() =>
              chatBoxRef.current.scrollTo({
                top: chatBoxRef.current.scrollHeight,
                behavior: "smooth",
              })
            }
          >
            ↓ New Messages
          </button>
        )}

        <div ref={chatEndRef} />
      </div>

      <div className="input-box">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

export default App;

