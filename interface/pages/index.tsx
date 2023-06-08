// --- React Methods
import React, { useContext, useEffect, useRef } from "react";
import {
  HashRouter as Router,
  Routes,
  Route,
  redirect,
} from "react-router-dom";
import RequireAuth from "../components/RequireAuth";

// --- Components
import Dashboard from "../components/Dashboard";
import CommunityList from "../components/CommunityList";
import APIKeyList from "../components/APIKeyList";
import NewScorer from "../components/NewScorer";
import LandingPage from "../components/LandingPage";
import Maintenance from "../components/Maintenance";

// --- Context
import { UserContext } from "../context/userContext";
import { useToast } from "@chakra-ui/react";

import PageLayout from "../components/PageLayout";
import HomePageLayout from "../components/HomePageLayout";
import NoMatch from "../components/NoMatch";
import { successToast } from "../components/Toasts";
import { isServerOnMaintenance } from "../utils/interceptors";

// Layout Route pattern from https://reactrouter.com/en/main/start/concepts#layout-routes
export const PageRoutes = () => (
  <Routes>
    <Route element={<HomePageLayout />}>
      <Route path="/" element={<LandingPage />} />
    </Route>
    <Route element={<PageLayout />}>
      <Route path="/dashboard" element={<Dashboard />}>
        <Route path="/dashboard/scorer" element={<CommunityList />} />
        <Route path="/dashboard/api-keys" element={<APIKeyList />} />
      </Route>
      <Route path="/new-scorer" element={<NewScorer />} />
    </Route>
    <Route path="*" element={<NoMatch />} />
  </Routes>
);

const PageRouter = () => {
  if (isServerOnMaintenance()) {
    return <Maintenance />;
  }

  const { loginComplete } = useContext(UserContext);
  const toast = useToast();

  useEffect(() => {
    if (loginComplete) {
      toast(successToast("Ethereum account has been validated.", toast));
    }
  }, [loginComplete]);

  if (isServerOnMaintenance()) {
    return <Maintenance />;
  }

  return (
    <Router>
      <RequireAuth>
        <PageRoutes />
      </RequireAuth>
    </Router>
  );
};

export default PageRouter;
