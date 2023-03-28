import { PageRoutes } from "../pages/index";

import { MemoryRouter } from "react-router-dom";
import {
  renderWithContext,
  makeTestUserContext,
} from "./userContextTestHelper";
import { UserState } from "../context/userContext";

const mockUserContext: UserState = makeTestUserContext();

export const renderApp = (startingPath: string) =>
  renderWithContext(
    mockUserContext,
    <MemoryRouter initialEntries={[startingPath]}>
      <PageRoutes />
    </MemoryRouter>
  );
