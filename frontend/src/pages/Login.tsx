import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { login } from "../services/api";
import { jwtDecode } from "jwt-decode";

interface JwtPayload {
  sub: string;
  email: string;
  role: string;
  exp: number;
}

export default function Login() {
  const { role } = useParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    try {
      const data = await login(email, password);
      localStorage.setItem("token", data.token);
      const decoded = jwtDecode<JwtPayload>(data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      // Redirect based on role from token
      navigate(`/dashboard/${decoded.role}`);
    } catch (e: any) {
      alert(e.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
      <div className="bg-slate-800 p-8 rounded-2xl w-96 border border-slate-700 shadow-xl">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 text-slate-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>

        <h2 className="text-2xl font-bold mb-6 capitalize">{role} Login</h2>

        <input
          placeholder="Email"
          type="email"
          className="w-full mb-3 p-3 bg-slate-700 rounded-lg border border-slate-600 focus:border-blue-500 outline-none transition-colors"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full mb-4 p-3 bg-slate-700 rounded-lg border border-slate-600 focus:border-blue-500 outline-none transition-colors"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button
          onClick={handleLogin}
          disabled={loading}
          className="w-full bg-blue-500 hover:bg-blue-600 disabled:opacity-50 py-3 rounded-lg font-medium transition-colors"
        >
          {loading ? "Logging in..." : "Login"}
        </button>
      </div>
    </div>
  );
}
