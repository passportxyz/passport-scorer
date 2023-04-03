// --- React components/methods
import React, { useEffect, useContext } from "react";

import { useNavigate, useLocation } from "react-router-dom";

import { UserContext } from "../context/userContext";

import { useApi } from "../hooks/useApi";

const RequireAuth = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { ready, connected, logout } = useContext(UserContext);

  useApi(logout);

  // If the user is not connected, redirect to the home page
  useEffect(() => {
    if (pathname !== "/" && ready && !connected) {
      navigate("/");
    }
  }, [ready, connected, pathname, navigate]);

  return <>{children}</>;
};

export default RequireAuth;
