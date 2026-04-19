import { createBrowserRouter, Navigate } from "react-router-dom";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import BotDetail from "@/pages/BotDetail";
import Audit from "@/pages/Audit";
import NotFound from "@/pages/NotFound";

export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  { path: "/dashboard", element: <Dashboard /> },
  { path: "/bots/:slug", element: <BotDetail /> },
  { path: "/audit", element: <Audit /> },
  { path: "/404", element: <NotFound /> },
  { path: "*", element: <Navigate to="/404" replace /> },
]);
