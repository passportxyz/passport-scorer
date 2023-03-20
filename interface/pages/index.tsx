// --- React Methods
import React, { useState, useRef, useContext, useEffect } from "react";
import {
  HashRouter as Router,
  Routes,
  Route,
  useNavigate,
} from "react-router-dom";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";
import Dashboard from "../components/Dashboard";
import Community from "../components/Community";
import CommunityList from "../components/CommunityList";
import APIKeyList from "../components/APIKeyList";
import NewScorer from "../pages/new-scorer";

// --- Pages
import LandingPage from "./landing";

// --- Context
import { UserContext } from "../context/userContext";
import { useToast } from "@chakra-ui/react";

export default function Home() {
  const { connected, authenticating, login, loginComplete } =
    useContext(UserContext);
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

  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
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
      </Routes>
    </Router>
  );
}
