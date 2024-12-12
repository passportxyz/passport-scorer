// User classes should define data that describes a "user" of one particular API,
// for example a PassportUIUser class that defines a user of the Passport UI API
// (i.e. someone with a particular address and DID)

// Supports any future requirements for all User types, like an ID
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface User {}

// Facilitates a generic User class, as well as a
// singleton instance pattern for creating/using
// a single instance of each derived User class
export abstract class BaseUser implements User {
  singletonInstance?: BaseUser;

  // "this" is a magic parameter in typescript for static
  // functions, telling the function what type of class
  // to expect to be called with
  static async get<T extends BaseUser>(this: { new (): T; singletonInstance?: T }): Promise<T> {
    if (!this.singletonInstance) {
      const singletonInstance = new this();
      await singletonInstance.init();
      this.singletonInstance = singletonInstance;
      return singletonInstance;
    }
    return this.singletonInstance;
  }

  protected abstract init(): Promise<void>;
}
