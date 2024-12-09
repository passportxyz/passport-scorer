import { createTestDIDSession } from '../utils/dids';
import { DID } from 'dids';
import { BaseUser } from './User';

export class PassportUIUser extends BaseUser {
  declare did: DID;
  declare address: string;
  scorerId: string = process.env.TEST_UI_SCORER_ID as string;

  async init() {
    const { did, address } = await createTestDIDSession();
    this.did = did;
    this.address = address;
  }
}
