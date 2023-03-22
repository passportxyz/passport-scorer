import React from "react";
import { screen, waitFor } from "@testing-library/react";
import Dashboard from "../../components/Dashboard";
import PageLayout from "../../components/PageLayout";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import {
  renderWithContext,
  makeTestUserContext,
} from "../../__test-fixtures__/userContextTestHelper";
import { UserState } from "../../context/userContext";

const mockUserContext: UserState = makeTestUserContext();

describe("Dashboard", () => {
  it("should render the correct dashboard tab", async () => {
    renderWithContext(
      mockUserContext,
      <MemoryRouter initialEntries={["/dashboard/api-keys"]}>
        <Routes>
          <Route element={<PageLayout />}>
            <Route path="/dashboard" element={<Dashboard />}>
              <Route path="/dashboard/scorer" element={<div />} />
              <Route path="/dashboard/api-keys" element={<div />} />
            </Route>
          </Route>
        </Routes>
      </MemoryRouter>
    );
    const activeTab = screen.getByTestId("api-keys-tab");
    const notActiveTab = screen.getByTestId("scorer-tab");
    await waitFor(async () => {
      expect(activeTab).toHaveClass(
        "flex w-full items-center justify-start rounded-md px-3 py-2 text-blue-darkblue border border-gray-lightgray bg-white"
      );
      expect(notActiveTab).toHaveClass(
        "flex w-full items-center justify-start rounded-md px-3 py-2 text-blue-darkblue mb-2"
      );
    });
  });
});
