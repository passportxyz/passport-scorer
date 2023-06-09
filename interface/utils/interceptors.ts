import axios, { AxiosError } from "axios";

export const unAuthorizedInterceptor = (logout: () => void) => {
  const interceptor = axios.interceptors.response.use(
    (response) => {
      return response;
    },
    (error: AxiosError) => {
      if (error.response?.status === 401) {
        logout();
      }
      return Promise.reject(error);
    }
  );

  return () => {
    axios.interceptors.response.eject(interceptor);
  };
};

export const headerInterceptor = () => {
  const requestInterceptor = axios.interceptors.request.use((config) => {
    const token = localStorage.getItem("access-token");
    if (config && config.headers && token) {
      config.headers["Content-Type"] = "application/json";
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  });

  return () => {
    axios.interceptors.response.eject(requestInterceptor);
  };
};

/**
 * Checks if the server is on maintenance mode.
 *
 * @returns True if the server is on maintenance mode, false otherwise.
 */
export const isServerOnMaintenance = () => {
  if (process.env.NEXT_PUBLIC_MAINTENANCE_MODE_ON) {
    try {
      const maintenancePeriod = JSON.parse(
        process.env.NEXT_PUBLIC_MAINTENANCE_MODE_ON
      );
      const start = new Date(maintenancePeriod[0]);
      const end = new Date(maintenancePeriod[1]);
      const now = new Date();

      return now >= start && now <= end;
    } catch (error) {
      return false;
    }
  }

  return false;
};
