import axios from "axios";

export const createApiKey = async (name: string) => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await axios.post(
      `${SCORER_BACKEND}account/api-key`,
      { name },
      {
        headers: {
          "Content-Type": "application/json",
          AUTHORIZATION: `Bearer ${token}`,
        },
      }
    );
    const { data } = await response;
  } catch (error) {
    throw error;
  }
};

export type ApiKeys = {
  id: string;
  name: string;
};

export const getApiKeys = async (): Promise<ApiKeys[]> => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await axios.get(`${SCORER_BACKEND}account/api-key`, {
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });

    const { data } = response;
    return data;
  } catch (error) {
    throw error;
  }
};

export type Community = {
  name: string;
  description: string;
};

export const createCommunity = async (community: Community) => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await axios.post(
      `${SCORER_BACKEND}account/communities`,
      { ...community },
      {
        headers: {
          "Content-Type": "application/json",
          AUTHORIZATION: `Bearer ${token}`,
        },
      }
    );
  } catch (error) {
    throw error;
  }
};

export const getCommunities = async (): Promise<Community[]> => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await axios.get(`${SCORER_BACKEND}account/communities`, {
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });

    const { data } = response;
    return data;
  } catch (error) {
    throw error;
  }
};
