import { useNavigate } from "react-router-dom";

export default function Home() {
  const navigate = useNavigate();

  const roles = [
    { name: "Patient", color: "bg-blue-500 hover:bg-blue-600" },
    { name: "Doctor", color: "bg-green-500 hover:bg-green-600" },
    { name: "Professional", color: "bg-purple-500 hover:bg-purple-600" },
    { name: "Admin", color: "bg-red-500 hover:bg-red-600" },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center p-6">
      <h1 className="text-4xl font-bold mb-4 text-center">
        Welcome to AI Health CRM
      </h1>

      <p className="text-slate-400 mb-10 text-center max-w-xl">
        Manage patients, appointments, and AI-powered healthcare insights in one place.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {roles.map((role) => (
          <div
            key={role.name}
            className="bg-slate-800 p-6 rounded-2xl shadow-lg text-center border border-slate-700"
          >
            <h2 className="text-xl font-semibold mb-4">{role.name}</h2>

            <button
              onClick={() => navigate(`/login/${role.name.toLowerCase()}`)}
              className={`w-full mb-2 py-2 rounded transition-colors ${role.color}`}
            >
              Login
            </button>

            <button
              onClick={() => navigate(`/signup/${role.name.toLowerCase()}`)}
              className="w-full py-2 rounded border border-slate-500 hover:bg-slate-700 transition-colors"
            >
              Sign Up
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
