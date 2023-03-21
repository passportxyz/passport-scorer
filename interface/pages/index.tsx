// --- React Methods
import React, { useContext, useEffect } from "react";
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

// --- Context
import { UserContext } from "../context/userContext";
import { useToast } from "@chakra-ui/react";

import PageLayout from "../components/PageLayout";
import HomePageLayout from "../components/HomePageLayout";
import NoMatch from "../components/NoMatch";

const PageRouter = () => {
  const { loginComplete } = useContext(UserContext);
  const toast = useToast();

  useEffect(() => {
    if (loginComplete) {
      toast({
        duration: 5000,
        isClosable: true,
        render: (result: any) => (
          <div className="flex justify-between rounded-md bg-blue-darkblue p-4 text-white">
            <span className="step-icon step-icon-completed flex h-9 items-center">
              <span className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-teal-600">
                <img
                  alt="completed icon"
                  className="sticky top-0 h-6"
                  src="/assets/white-check-icon.svg"
                />
              </span>
            </span>
            <p className="py-1 px-3">Ethereum account has been validated.</p>
            <button className="sticky top-0" onClick={result.onClose}>
              <img
                alt="close button"
                className="rounded-lg hover:bg-gray-500"
                src="/assets/x-icon.svg"
              />
            </button>
          </div>
        ),
      });
    }
  }, [loginComplete]);

  // Layout pattern from https://reactrouter.com/en/main/start/concepts#layout-routes

  return (
    <Router>
      <RequireAuth>
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
      </RequireAuth>
    </Router>
  );
};

export default PageRouter;
