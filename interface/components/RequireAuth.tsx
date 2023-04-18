// --- React components/methods
import React, { useEffect, useContext, useLayoutEffect } from "react";

import { useNavigate, useLocation } from "react-router-dom";

import { UserContext } from "../context/userContext";

import {
  headerInterceptor,
  unAuthorizedInterceptor,
} from "../utils/interceptors";

const testingCypress =
  process.env.NEXT_PUBLIC_PASSPORT_SCORER_TESTING_CYPRESS === "on";

const RequireAuth = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { ready, connected, logout } = useContext(UserContext);

  useLayoutEffect(() => {
    unAuthorizedInterceptor(logout);
    headerInterceptor();
  }, []);

  // If the user is not connected, redirect to the home page
  useEffect(() => {
    if (pathname !== "/" && ready && !connected && !testingCypress) {
      navigate("/");
    }
  }, [ready, connected, pathname, navigate]);

  return <>{children}</>;
};

export default RequireAuth;
