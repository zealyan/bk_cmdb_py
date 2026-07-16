package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.mongodb.org/mongo-driver/mongo/readpref"

	"configcenter/src/scene_server/admin_server/upgrader"
	"configcenter/src/storage/dal/mongo/local"
	"configcenter/src/storage/dal/redis"
	"configcenter/src/ac/iam"

	_ "configcenter/src/scene_server/admin_server/upgrader/history/v3.0.8"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/v3.0.9-beta.1"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/v3.0.9-beta.3"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/v3.1.0-alpha.2"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x08.09.04.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x08.09.17.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x08.09.18.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x08.09.26.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.09.30.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.10.10.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.10.30.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.11.19.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.02"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.03"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.04"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.05"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.12.06"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x18.12.13.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.01.18.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.02.15.10"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.04.16.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.04.16.02"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.04.16.03"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.05.16.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.08.19.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.08.20.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.08.26.02"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.02"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.03"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.04"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.05"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.06"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.07"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.09.03.08"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.10.22.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.10.22.02"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x19.10.22.03"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x20.01.13.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/x20.02.17.01"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201909062359"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201909272359"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201910091234"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201911121930"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201911122106"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201911141015"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201911141516"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201911261109"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.6.201912241627"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.7.201911141719"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.7.201912121117"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.7.201912171427"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.7.202002231026"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202001172032"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202004141131"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202004151435"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202004241035"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202004291536"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202006021120"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202006092135"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202006231730"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202006241144"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202006281530"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202007011748"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202008051650"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202008111026"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202008241747"
	_ "configcenter/src/scene_server/admin_server/upgrader/history/y3.8.202009101702"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202002131522"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202008101530"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202008121631"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202008172134"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202010131456"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202010151455"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202010151650"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202010211805"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202010281615"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011021415"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011021501"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011171550"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011172152"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011192014"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011201146"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011241510"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011251014"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202011301723"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202012011450"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202101061721"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202102011055"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202102261105"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202103031533"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202103231621"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202104011012"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202104211151"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202105261459"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202106031151"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202106291420"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202106301910"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202107011154"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202107161611"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202107271940"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202107301510"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202107311844"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202112061431"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202112071130"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.9.202112071431"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202104221702"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202105251041"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202105261459"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202106031151"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107011735"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107021056"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107161611"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107271945"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107301510"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202107311844"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202109181134"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202112071130"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202112071431"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202112171521"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202202181012"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202203011516"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202203021455"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202203031512"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202204181447"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202204271725"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202205182148"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202206081408"
	_ "configcenter/src/scene_server/admin_server/upgrader/y3.10.202209231617"
)

func main() {
	ctx := context.Background()
	uri := "mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb"
	dbName := "cmdb"
	conf := local.MongoConf{
		URI:            uri,
		RsName:         "rs0",
		TimeoutSeconds: 30,
		SocketTimeout:  30,
		MaxOpenConns:   10,
		MaxIdleConns:   10,
	}
	db, err := local.NewMgo(conf, 30*time.Second)
	if err != nil {
		panic(fmt.Sprintf("NewMgo failed: %v", err))
	}
	if err := db.Ping(); err != nil {
		panic(fmt.Sprintf("Ping failed: %v", err))
	}

	// 跳过两个 Redis/IAM 注册的版本包（不动属性），其余全跑
	var cache redis.Client
	var iamObj *iam.IAM
	_, _, err = upgrader.Upgrade(ctx, db, cache, iamObj, &upgrader.Config{OwnerID: "0", User: "admin"})
	if err != nil {
		panic(fmt.Sprintf("Upgrade failed: %v", err))
	}

	// 用原生 driver 读回权威终态
	cli, err := mongo.Connect(ctx, options.Client().ApplyURI(uri))
	if err != nil {
		panic(fmt.Sprintf("mongo connect failed: %v", err))
	}
	defer cli.Disconnect(ctx)
	if err := cli.Ping(ctx, readpref.Primary()); err != nil {
		panic(fmt.Sprintf("ping failed: %v", err))
	}
	coll := cli.Database(dbName)

	// 对象数
	objs, err := coll.Collection("cc_ObjDes").Find(ctx, bson.M{})
	if err != nil {
		panic(err)
	}
	var objDocs []bson.M
	objs.All(ctx, &objDocs)
	fmt.Printf("OBJECTS_COUNT=%d\n", len(objDocs))
	for _, o := range objDocs {
		fmt.Printf("OBJECT %v name=%v\n", o["bk_obj_id"], o["bk_obj_name"])
	}

	// 属性总数 + 按对象分布
	cur, err := coll.Collection("cc_ObjAttDes").Find(ctx, bson.M{})
	if err != nil {
		panic(err)
	}
	var attrs []bson.M
	cur.All(ctx, &attrs)
	fmt.Printf("ATTRS_COUNT=%d\n", len(attrs))

	byObj := map[string]int{}
	for _, a := range attrs {
		oid, _ := a["bk_obj_id"].(string)
		byObj[oid]++
	}
	fmt.Println("ATTRS_BY_OBJECT:")
	for k, v := range byObj {
		fmt.Printf("  %s=%d\n", k, v)
	}

	// 完整属性导出（供回填 Python）
	out, _ := json.MarshalIndent(attrs, "", "  ")
	fmt.Printf("ATTRS_JSON_START\n%s\nATTRS_JSON_END\n", string(out))
}
