import axios from "axios";

const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;

export const createApiKey = async (name: string) => {
  try {
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
  prefix: string;
  name: string;
  created: string;
};

export const getApiKeys = async (): Promise<ApiKeys[]> => {
  try {
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

export const deleteApiKey = async (
  apiKeyId: ApiKeys["prefix"]
): Promise<void> => {
  try {
    const token = localStorage.getItem("access-token");
    await axios.delete(`${SCORER_BACKEND}account/api-key/${apiKeyId}`, {
      headers: {
        AUTHORIZATION: `Bearer ${token}`,
      },
    });
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
