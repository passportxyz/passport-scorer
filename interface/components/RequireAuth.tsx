// --- React components/methods
import React, { useEffect, useContext } from "react";

import { useRouter } from "next/router";

import { UserContext } from "../context/userContext";

const RequireAuth = ({ children }: { children: React.ReactNode }) => {
  const { pathname, push } = useRouter();
  const { ready, connected } = useContext(UserContext);

  // If the user is not connected, redirect to the home page
  useEffect(() => {
    if (pathname !== "/" && ready && !connected) {
      push("/");
    }
  }, [ready, connected, pathname, push]);

  return <>{children}</>;
};

export default RequireAuth;
