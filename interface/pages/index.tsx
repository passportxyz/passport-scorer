// --- React Methods
import React from "react";
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import RequireAuth from "../components/RequireAuth";

// --- Components
import Dashboard from "../components/Dashboard";
import CommunityList from "../components/CommunityList";
import APIKeyList from "../components/APIKeyList";
import NewScorer from "../pages/new-scorer";
import LandingPage from "../components/LandingPage";

import PageLayout from "../components/PageLayout";
import HomePageLayout from "../components/HomePageLayout";

// Layout pattern from https://reactrouter.com/en/main/start/concepts#layout-routes

const PageRouter = () => {
  return (
    <Router>
      <RequireAuth>
        <Routes>
          <Route element={<HomePageLayout />}>
            <Route path="/" element={<LandingPage />} />
          </Route>
          <Route element={<PageLayout />}>
            <Route
              path="/dashboard/scorer"
              element={
                <Dashboard activeTab="scorer">
                  <CommunityList />
                </Dashboard>
              }
            />
            <Route
              path="/dashboard/api-keys"
              element={
                <Dashboard activeTab="api-keys">
                  <APIKeyList />
                </Dashboard>
              }
            />
            <Route path="/new-scorer" element={<NewScorer />} />
          </Route>
        </Routes>
      </RequireAuth>
    </Router>
  );
};

export default PageRouter;
