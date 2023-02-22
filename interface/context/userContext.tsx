import { createContext, useState, useReducer, useEffect } from "react";

import { useConnectWallet } from "@web3-onboard/react";
import { OnboardAPI, WalletState } from "@web3-onboard/core";
import { initWeb3Onboard } from "../utils/onboard";

import { SiweMessage } from "siwe";

export interface UserState {
  loggedIn: boolean;
  message: string;
  signature: string;
  login: () => Promise<void>;
  logout: (wallet: WalletState) => Promise<void>;
  web3OnBoard?: OnboardAPI;
}

export const initialState: UserState = {
  loggedIn: false,
  message: "",
  signature: "",
  login: async () => {},
  logout: async (wallet: WalletState) => {},
};

enum UserActions {
  LOGIN = "LOGIN",
  LOGOUT = "LOGOUT",
  SET_WEB3_ONBOARD = "SET_WEB3_ONBOARD",
}

const userReducer = (
  state: UserState,
  action: { type: UserActions; payload: any }
) => {
  switch (action.type) {
    case UserActions.LOGIN:
      return {
        ...state,
        loggedIn: true,
      };
    case UserActions.LOGOUT:
      return {
        ...state,
        loggedIn: false,
      };
    case UserActions.SET_WEB3_ONBOARD:
      return {
        ...state,
        web3OnBoard: action.payload,
      };
    default:
      return state;
  }
};

export const UserContext = createContext(initialState);

export const UserProvider = ({ children }: { children: any }) => {
  const [state, dispatch] = useReducer(userReducer, initialState);
  const [{ wallet, connecting }, connect, disconnect] = useConnectWallet();

  const login = async () => {
    await connect();
    // const siwe = new SiweMessage();
    // const message = siwe.createMessage();
    // const signature = await siwe.signMessage(message);
    // dispatch({
    //   type: UserActions.LOGIN,
    //   payload: {
    //     message,
    //     signature,
    //   }
    // })
  };

  const logout = async (wallet: WalletState) => {
    await disconnect(wallet);
    dispatch({
      type: UserActions.LOGOUT,
      payload: null,
    });
  };

  // Init onboard to enable hooks
  useEffect((): void => {
    dispatch({
      type: UserActions.SET_WEB3_ONBOARD,
      payload: initWeb3Onboard,
    });
  }, []);

  return (
    <UserContext.Provider value={{ ...state, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};
