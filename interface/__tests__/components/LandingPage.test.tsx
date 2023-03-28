import { waitFor, render } from "@testing-library/react";
import LandingPage from "../../components/LandingPage";
import { UserContext } from "../../context/userContext";
import {
  renderWithContext,
  makeTestUserContext,
} from "../../__test-fixtures__/userContextTestHelper";
import { UserState } from "../../context/userContext";
import { MemoryRouter } from "react-router-dom";

describe("LandingPage", () => {
  it("should disable SIWE button while loading existing login", async () => {
    const mockUserContext: UserState = makeTestUserContext({ ready: false });
    const { getAllByText } = renderWithContext(
      mockUserContext,
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(getAllByText("Loading...")[0].closest("button")).toBeDisabled();
  });

  it("should enable SIWE button once ready", async () => {
    const mockUserContext: UserState = makeTestUserContext({ ready: true });
    const { getAllByText } = renderWithContext(
      mockUserContext,
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(
      getAllByText("Sign-in with Ethereum")[0].closest("button")
    ).toBeEnabled();
  });
});
