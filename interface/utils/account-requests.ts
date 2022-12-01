export const createApiKey = async (name: string) => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await fetch(`${SCORER_BACKEND}account/api-key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
      body: JSON.stringify({ name }),
    });
    const data = await response.json();
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
    const response = await fetch(`${SCORER_BACKEND}account/api-key`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });

    const data = await response.json();
    return data;
  } catch (error) {
    throw error;
  }
};
