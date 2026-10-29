const {PGlite}=require('@electric-sql/pglite');
const fs=require('fs');
const path=require('path');
(async()=>{
 const db=new PGlite();
 const sql=fs.readFileSync(path.join(__dirname,'..','database','schema.sql'),'utf8');
 await db.exec('CREATE ROLE anon; CREATE ROLE authenticated;');
 await db.exec(sql); await db.exec(sql);
 const tables=await db.query("SELECT relname,relrowsecurity FROM pg_class WHERE relname IN ('customers','transactions','predictions','fraud_alerts')");
 if(tables.rows.length!==4||tables.rows.some(r=>!r.relrowsecurity))throw Error('Missing tables or RLS');
 await db.exec("INSERT INTO customers(id,name,email,created_at) VALUES (200,'Demo','demo@example.com',now()); SELECT setval(pg_get_serial_sequence('customers','id'),(SELECT max(id) FROM customers),true);");
 const result=await db.query("INSERT INTO customers(name,email,created_at) VALUES ('Next','next@example.com',now()) RETURNING id");
 if(result.rows[0].id!==201)throw Error('Sequence reset failed');
 let fk=false;try{await db.exec("INSERT INTO predictions(transaction_id,fraud_probability,predicted_fraud,risk_level,model_version,explanation) VALUES(999,0.9,true,'high','test','[]');");}catch(e){fk=e.code==='23503';}
 if(!fk)throw Error('FK not enforced');
 await db.exec('SET ROLE anon');
 let blocked=false;try{await db.query('SELECT * FROM customers')}catch(e){blocked=e.code==='42501'}
 if(!blocked)throw Error('anon access not blocked');
 await db.close();console.log('PASS: PostgreSQL schema, repeat initialization, RLS, foreign keys, sequence reset and anonymous access restriction (PGlite).');
})();
