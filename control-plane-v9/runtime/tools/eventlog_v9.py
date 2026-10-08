import json,hashlib,datetime
def append_event(con,event_type,object_type,object_id,payload):
    payload_json=json.dumps(payload,sort_keys=True,separators=(",",":"))
    event_key=hashlib.sha256((event_type+"|"+object_type+"|"+object_id+"|"+payload_json).encode()).hexdigest()
    event_id="evt:"+event_key
    if con.execute("SELECT 1 FROM events WHERE event_id=?",(event_id,)).fetchone():
        return event_id,False
    prev=con.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
    prevh=prev[0] if prev else ""
    created=datetime.datetime.now(datetime.timezone.utc).isoformat()
    body=json.dumps({"event_id":event_id,"event_type":event_type,"object_type":object_type,"object_id":object_id,
                     "created_at":created,"payload":payload,"previous_event_hash":prevh},
                    sort_keys=True,separators=(",",":"))
    eh=hashlib.sha256(body.encode()).hexdigest()
    con.execute("""INSERT INTO events(event_id,event_type,object_type,object_id,created_at,payload_json,previous_event_hash,event_hash)
                   VALUES(?,?,?,?,?,?,?,?)""",(event_id,event_type,object_type,object_id,created,payload_json,prevh or None,eh))
    return event_id,True
