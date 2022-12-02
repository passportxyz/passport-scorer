import axios from "axios";

export const createApiKey = async (name: string) => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await axios.post(
      `${SCORER_BACKEND}account/api-key`,
      { data: { name } },
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
  created: string;
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

export const deleteApiKey = async (apiKeyId: ApiKeys["id"]) => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");

    const response = await fetch(`${SCORER_BACKEND}account/api-key/${apiKeyId}`, {
      method: "DELETE",
      headers: {
        AUTHORIZATION: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    return data;
  } catch (error) {
    throw error;
  }
};
